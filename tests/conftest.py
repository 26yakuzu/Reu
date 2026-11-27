import pytest

from terrasense.geo.boundary import ADM0_PATH
from terrasense.geo.layers import current_dir

HAS_BOUNDARY = ADM0_PATH.exists()
HAS_PROCESSED = current_dir().exists()

needs_boundary = pytest.mark.skipif(not HAS_BOUNDARY, reason="real boundary not fetched (python -I scripts/fetch.py)")
needs_processed = pytest.mark.skipif(not (HAS_BOUNDARY and HAS_PROCESSED), reason="processed data absent (scripts/prepare.py)")
