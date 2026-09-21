"""Worker process bootstrap: cap BLAS/OpenMP before NumPy import.

Import this module first in every spawn worker. Do not import NumPy above this
file in a worker entrypoint.
"""

from __future__ import annotations

import os

for _k in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[_k] = "1"


def apply() -> dict[str, str]:
    for k in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        os.environ[k] = "1"
    return {k: os.environ[k] for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
