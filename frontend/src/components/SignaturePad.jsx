import { forwardRef } from 'react';

import PropTypes from 'prop-types';
import SignatureCanvas from 'react-signature-canvas';

const SignaturePad = forwardRef(function SignaturePad({ onClear }, ref) {
  return (
    <div className="glass-card p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="section-label">Signature</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">Draw to confirm your agreement</h3>
        </div>
        <button type="button" className="secondary-button" onClick={onClear} aria-label="Clear signature">
          Clear
        </button>
      </div>
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
        <SignatureCanvas
          ref={ref}
          penColor="#0f172a"
          canvasProps={{
            width: 900,
            height: 280,
            className: 'w-full h-[280px] bg-white',
            'aria-label': 'Signature pad',
          }}
        />
      </div>
    </div>
  );
});

SignaturePad.propTypes = {
  onClear: PropTypes.func.isRequired,
};

export default SignaturePad;
