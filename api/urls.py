
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OperatorRoleViewSet,
    OperatorViewSet,
    ComponentViewSet,
    BinViewSet,
    AssemblyTypeViewSet,
    AssemblyComponentViewSet,
    AssemblyStepViewSet,
    StepRequiredComponentViewSet,
    EventLogViewSet,
    StepObjectViewSet,
    AssemblyExecutionViewSet,
    StepExecutionViewSet,
    ErrorTypeViewSet,
    ErrorLogViewSet,
)

router = DefaultRouter()
router.register(r"operator-roles", OperatorRoleViewSet)
router.register(r"operators", OperatorViewSet)
router.register(r"components", ComponentViewSet)
router.register(r"bins", BinViewSet)
router.register(r"assembly-types", AssemblyTypeViewSet)
router.register(r"assembly-components", AssemblyComponentViewSet)
router.register(r"assembly-steps", AssemblyStepViewSet)
router.register(r"step-required-components", StepRequiredComponentViewSet)
router.register(r"event-logs", EventLogViewSet)
router.register(r"step-objects", StepObjectViewSet)
router.register(r"assembly-executions", AssemblyExecutionViewSet)
router.register(r"step-executions", StepExecutionViewSet)
router.register(r"error-types", ErrorTypeViewSet)
router.register(r"errors", ErrorLogViewSet)



urlpatterns = [
    path("", include(router.urls)),
]

