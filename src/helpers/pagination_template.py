from math import ceil
from typing import Dict

def build_pagination_meta(
    *,
    page: int,
    page_size: int,
    total_items: int,
) -> Dict[str, int]:
    """
    Pagination metadata template.
    total_pages is always derived from total_items and page_size.
    """
    total_pages = ceil(total_items / page_size) if page_size > 0 else 0

    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }
