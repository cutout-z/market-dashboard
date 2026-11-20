"""forex's year-start lookup must not warn. pandas (dtypes/common.py) sets
simplefilter("always", DeprecationWarning) inside catch_warnings(), which is not
thread-safe, so under the threaded live service the filter could stick at
"always" and this lookup then printed one warning per timestamp: most of a
44 GB log by Nov 2026."""

import warnings
from datetime import datetime, timezone

from app.sources.forex import ForexSource


def test_first_current_year_index_no_warning():
    year = datetime.now(timezone.utc).year
    last_year = int(datetime(year - 1, 12, 30, tzinfo=timezone.utc).timestamp())
    this_year = int(datetime(year, 1, 2, tzinfo=timezone.utc).timestamp())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        idx = ForexSource._first_current_year_index([last_year, this_year], 2)
    assert idx == 1
