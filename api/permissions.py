from rest_framework.permissions import BasePermission, SAFE_METHODS

class RolePermission(BasePermission):
    """
    Base class: checks if the authenticated user has at least one of `required_roles`.
    Subclasses just set `required_roles = [...]`.
    """
    required_roles: list[str] = []

    allow_read_only_for_all = True  # can be overridden in subclasses

    def has_permission(self, request, view):
        # Allow read-only access for everyone logged in, if configured
        if self.allow_read_only_for_all and request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # User must be linked to an Operator
        operator = getattr(user, "operator_profile", None)
        if operator is None:
            return False

        # Get all role names for this operator
        user_roles = set(
            operator.roles.values_list("role_name", flat=True)
        )

        # If no specific roles required, deny by default
        if not self.required_roles:
            return False

        # Check intersection
        return any(role in user_roles for role in self.required_roles)

class ManagementOnly(RolePermission):
    required_roles = ["Management"]


class ManagementOrService(RolePermission):
    required_roles = ["Management", "Servis"]


class OperatorsCanWrite(RolePermission):
    required_roles = ["Operátor", "Management"]
    allow_read_only_for_all = True