"""Paginación por defecto de la API

'PageNumberPagination' divide el tamño de pagina PAGE_SIZE global.

"""

from rest_framework.pagination import PageNumberPagination

class DefaultPagination(PageNumberPagination):
    """El parametro del tamaño de las paginas. """
    page_size_query_param = "page_size"
    max_page_size = 200

__all__ = ["DefaultPagination"]