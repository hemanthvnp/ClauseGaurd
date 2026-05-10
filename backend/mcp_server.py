"""
ClauseGuard MCP Server
======================
Exposes ClauseGuard document analysis as MCP tools so any MCP client
(Claude Desktop, Cursor, etc.) can ask questions about legal documents.

Usage
-----
1. Install: pip install mcp
2. Run:     python mcp_server.py
3. Add to Claude Desktop config (~/.claude/claude_desktop_config.json):

   {
     "mcpServers": {
       "clauseguard": {
         "command": "python",
         "args": ["/path/to/backend/mcp_server.py"],
         "env": { "DATABASE_URL": "postgresql://clauseguard:clauseguard@localhost:5432/clauseguard" }
       }
     }
   }
"""
from __future__ import annotations

import os
import sys

# Ensure app package is importable when run as a standalone script
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://clauseguard:clauseguard@localhost:5432/clauseguard',
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Lazy import ORM models (avoids loading all of FastAPI at startup)
from app.models.schema import Clause, Document, User  # noqa: E402

server = Server('clauseguard')


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rag_search(clauses: list, keywords: list[str], limit: int = 8) -> list:
    kws = [k.lower() for k in keywords]
    scored = []
    for c in clauses:
        cat = (c.category or '').lower()
        body = f"{c.clause_text} {c.plain_english or ''}".lower()
        score = sum(3.0 if kw in cat else (1.0 if kw in body else 0.0) for kw in kws)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def _fmt(clauses: list) -> str:
    if not clauses:
        return 'No matching clauses found.'
    parts = []
    for c in clauses:
        parts.append(
            f"[{(c.risk_level or 'unknown').upper()}] {c.category or 'General'} "
            f"(score: {c.risk_score})\n"
            f"Text: {c.clause_text[:400]}\n"
            + (f"Summary: {c.plain_english}\n" if c.plain_english else '')
        )
    return '\n---\n'.join(parts)


def _get_clauses(document_id: str) -> tuple:
    with Session(engine) as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return None, []
        clauses = list(db.scalars(select(Clause).where(Clause.document_id == doc.id)).all())
        return doc, clauses


# ── Tool list ─────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name='list_documents',
            description='List all analyzed documents with their risk levels and scores.',
            inputSchema={'type': 'object', 'properties': {
                'user_email': {'type': 'string', 'description': 'Filter by user email (optional)'},
            }},
        ),
        types.Tool(
            name='get_document_overview',
            description='Get overall risk summary for a specific document.',
            inputSchema={'type': 'object', 'properties': {
                'document_id': {'type': 'string', 'description': 'Document UUID'},
            }, 'required': ['document_id']},
        ),
        types.Tool(
            name='search_clauses',
            description=(
                'RAG search — find clauses in a document matching keywords. '
                'Use for: financial risk, data privacy, termination, arbitration, non-compete, liability, etc.'
            ),
            inputSchema={'type': 'object', 'properties': {
                'document_id': {'type': 'string', 'description': 'Document UUID'},
                'keywords': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Search terms'},
                'limit': {'type': 'integer', 'default': 8},
            }, 'required': ['document_id', 'keywords']},
        ),
        types.Tool(
            name='get_clauses_by_risk',
            description='Get all clauses at a specific risk level for a document.',
            inputSchema={'type': 'object', 'properties': {
                'document_id': {'type': 'string', 'description': 'Document UUID'},
                'level': {'type': 'string', 'enum': ['critical', 'high', 'medium', 'low']},
            }, 'required': ['document_id', 'level']},
        ),
        types.Tool(
            name='get_clauses_by_category',
            description='Get clauses matching a category: Payment Terms, Indemnification, Arbitration, etc.',
            inputSchema={'type': 'object', 'properties': {
                'document_id': {'type': 'string', 'description': 'Document UUID'},
                'category': {'type': 'string'},
            }, 'required': ['document_id', 'category']},
        ),
        types.Tool(
            name='ask_document',
            description=(
                'Ask a natural language question about a document. '
                'Examples: "Is this risk free?", "Do I have financial risk?", "What happens if I want to leave?"'
            ),
            inputSchema={'type': 'object', 'properties': {
                'document_id': {'type': 'string', 'description': 'Document UUID'},
                'question': {'type': 'string'},
            }, 'required': ['document_id', 'question']},
        ),
    ]


# ── Tool handlers ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == 'list_documents':
        with Session(engine) as db:
            docs = list(db.scalars(select(Document).order_by(Document.created_at.desc()).limit(50)).all())
        if not docs:
            return [types.TextContent(type='text', text='No documents found.')]
        lines = [f"- [{d.overall_risk_level or '?'}] {d.filename} (score: {d.overall_risk_score}) — id: {d.id}"
                 for d in docs]
        return [types.TextContent(type='text', text='\n'.join(lines))]

    if name == 'get_document_overview':
        doc, clauses = _get_clauses(arguments['document_id'])
        if doc is None:
            return [types.TextContent(type='text', text='Document not found.')]
        counts = {l: sum(1 for c in clauses if c.risk_level == l) for l in ('critical', 'high', 'medium', 'low')}
        text = (
            f"Document: {doc.filename}\n"
            f"Overall risk: {doc.overall_risk_level} (score {doc.overall_risk_score}/100)\n"
            f"Clauses — Critical: {counts['critical']}, High: {counts['high']}, "
            f"Medium: {counts['medium']}, Low: {counts['low']}"
        )
        return [types.TextContent(type='text', text=text)]

    if name == 'search_clauses':
        doc, clauses = _get_clauses(arguments['document_id'])
        if doc is None:
            return [types.TextContent(type='text', text='Document not found.')]
        results = _rag_search(clauses, arguments.get('keywords', []), arguments.get('limit', 8))
        return [types.TextContent(type='text', text=_fmt(results))]

    if name == 'get_clauses_by_risk':
        doc, clauses = _get_clauses(arguments['document_id'])
        if doc is None:
            return [types.TextContent(type='text', text='Document not found.')]
        level = arguments.get('level', 'high')
        results = [c for c in clauses if c.risk_level == level]
        return [types.TextContent(type='text', text=_fmt(results))]

    if name == 'get_clauses_by_category':
        doc, clauses = _get_clauses(arguments['document_id'])
        if doc is None:
            return [types.TextContent(type='text', text='Document not found.')]
        cat = arguments.get('category', '').lower()
        results = [c for c in clauses if cat in (c.category or '').lower()]
        return [types.TextContent(type='text', text=_fmt(results))]

    if name == 'ask_document':
        doc, clauses = _get_clauses(arguments['document_id'])
        if doc is None:
            return [types.TextContent(type='text', text='Document not found.')]

        q = arguments.get('question', '').lower()
        financial_kws = ['payment', 'fee', 'cost', 'liability', 'damages', 'penalty',
                         'indemnif', 'revenue', 'charge', 'price', 'invoice', 'liquidated']
        data_kws = ['data', 'privacy', 'personal information', 'analytics', 'tracking']
        term_kws = ['terminat', 'cancel', 'exit', 'end', 'leave', 'break']

        if any(w in q for w in ['financial', 'money', 'pay', 'cost', 'fee', 'liab', 'damage']):
            hits = _rag_search(clauses, financial_kws, 6)
            risky = [c for c in hits if c.risk_level in ('critical', 'high')]
            if not hits:
                return [types.TextContent(type='text', text=f'No financial clauses found in {doc.filename}.')]
            if not risky:
                return [types.TextContent(type='text',
                    text=f'{doc.filename} has financial clauses but none are critical/high risk: '
                         f'{", ".join(c.category for c in hits if c.category)}.')]
            return [types.TextContent(type='text',
                text=f'Financial risk found in {doc.filename}:\n\n{_fmt(risky)}')]

        if any(w in q for w in ['data', 'privacy', 'personal']):
            hits = _rag_search(clauses, data_kws, 5)
            return [types.TextContent(type='text', text=_fmt(hits))]

        if any(w in q for w in ['terminat', 'cancel', 'leave', 'exit']):
            hits = _rag_search(clauses, term_kws, 5)
            return [types.TextContent(type='text', text=_fmt(hits))]

        risky = [c for c in clauses if c.risk_level in ('critical', 'high')]
        return [types.TextContent(type='text',
            text=f'{doc.filename}: {len(risky)} critical/high clauses. '
                 f'Overall: {doc.overall_risk_level} ({doc.overall_risk_score}/100).\n\n{_fmt(risky[:5])}')]

    return [types.TextContent(type='text', text=f'Unknown tool: {name}')]


# ── Run ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
