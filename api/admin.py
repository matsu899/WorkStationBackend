from django.contrib import admin
from .models import (
    Operator,
    OperatorRole,
    OperatorRoleAssignment,
    Component,
    Bin,
    AssemblyType,
    AssemblyComponent,
    AssemblyStep,
    StepRequiredComponent,
    StepObject,
    AssemblyExecution,
    StepExecution,
    ErrorType,
    ErrorLog,
    EventLog,
)


class OperatorRoleAssignmentInline(admin.TabularInline):
    model = OperatorRoleAssignment
    fk_name = "operator"
    extra = 1


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ("name", "employee_id", "user")
    search_fields = ("name", "employee_id")
    inlines = [OperatorRoleAssignmentInline]


@admin.register(OperatorRole)
class OperatorRoleAdmin(admin.ModelAdmin):
    list_display = ("role_name", "description")
    search_fields = ("role_name",)


@admin.register(OperatorRoleAssignment)
class OperatorRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("operator", "role", "assigned_at", "assigned_by", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("operator__name", "role__role_name")

