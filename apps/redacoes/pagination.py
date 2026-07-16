from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class RedacaoPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "redacoes": data,
                "total": self.page.paginator.count,
                "page": self.page.number,
                "limit": self.get_page_size(self.request),
            }
        )
