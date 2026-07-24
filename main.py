import os
# Limit CPU threads for PyTorch, NumPy, OpenMP, etc.
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

import onnxruntime as ort

# Monkeypatch ONNX Runtime to limit threads to 2 and force sequential execution
_original_InferenceSession = ort.InferenceSession
def _custom_InferenceSession(path_or_bytes, sess_options=None, *args, **kwargs):
    if sess_options is None:
        sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 2
    sess_options.inter_op_num_threads = 1
    sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return _original_InferenceSession(path_or_bytes, sess_options, *args, **kwargs)
ort.InferenceSession = _custom_InferenceSession

from gui import CookieRunAIApp

if __name__ == "__main__":
    app = CookieRunAIApp()
    app.mainloop()
