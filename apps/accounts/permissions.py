from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsAdminOrProfessor(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.user_type in {"admin", "professor"}


class IsAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.user_type == "admin" or user.is_superuser


class IsStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.user_type in {"admin", "professor", "corretor"}
