"""
URL konfigurace pro API aplikace
Definuje všechny API endpoints pro Django REST Framework
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # Serializery pro operátory a jejich role
    OperatorRoleViewSet,
    OperatorViewSet,
    # Serializery pro komponenty a zásobníky
    ComponentViewSet,
    BinViewSet,
    # Serializery pro typy sestav a jejich komponenty
    AssemblyTypeViewSet,
    AssemblyComponentViewSet,
    # Serializery pro kroky montáže
    AssemblyStepViewSet,
    StepRequiredComponentViewSet,
    # Serializery pro logování
    EventLogViewSet,
    # Serializery pro objekty v krocích
    StepObjectViewSet,
    # Serializery pro spouštění montáže
    AssemblyExecutionViewSet,
    StepExecutionViewSet,
    # Serializery pro chyby
    ErrorTypeViewSet,
    ErrorLogViewSet,
    # Serializery pro organizér
    OrganizerSlotStateViewSet
)

# DefaultRouter automaticky generuje CRUD operace pro registrované ViewSety
router = DefaultRouter()

# =============================================================================
# OPERÁTOR A ROLE - API ENDPOINTS
# =============================================================================
router.register(r"operator-roles", OperatorRoleViewSet)  # CRUD pro role operátorů
router.register(r"operators", OperatorViewSet)  # CRUD pro operátory

# =============================================================================
# KOMPONENTY A ZÁSOBNÍKY - API ENDPOINTS
# =============================================================================
router.register(r"components", ComponentViewSet)  # CRUD pro komponenty
router.register(r"bins", BinViewSet)  # CRUD pro zásobníky

# =============================================================================
# TYPY SESTAV A JEJICH KOMPONENTY - API ENDPOINTS
# =============================================================================
router.register(r"assembly-types", AssemblyTypeViewSet)  # CRUD pro typy sestav
router.register(r"assembly-components", AssemblyComponentViewSet)  # CRUD pro komponenty v sestavách

# =============================================================================
# KROKY MONTÁŽE - API ENDPOINTS
# =============================================================================
router.register(r"assembly-steps", AssemblyStepViewSet)  # CRUD pro kroky montáže
router.register(r"step-required-components", StepRequiredComponentViewSet)  # CRUD pro komponenty v krocích

# =============================================================================
# LOGOVÁNÍ UDÁLOSTÍ - API ENDPOINTS
# =============================================================================
router.register(r"event-logs", EventLogViewSet)  # CRUD pro záznam událostí

# =============================================================================
# OBJEKTY V KROCÍCH - API ENDPOINTS
# =============================================================================
router.register(r"step-objects", StepObjectViewSet)  # CRUD pro objekty (text/obrázky) v krocích

# =============================================================================
# SPOUŠTĚNÍ MONTÁŽE - API ENDPOINTS
# =============================================================================
router.register(r"assembly-executions", AssemblyExecutionViewSet)  # CRUD pro provádění montáží
router.register(r"step-executions", StepExecutionViewSet)  # CRUD pro provádění kroků

# =============================================================================
# CHYBY - API ENDPOINTS
# =============================================================================
router.register(r"error-types", ErrorTypeViewSet)  # CRUD pro typy chyb
router.register(r"errors", ErrorLogViewSet)  # CRUD pro protokol chyb

# =============================================================================
# ORGANIZÉR - API ENDPOINTS
# =============================================================================
router.register(r"organizer-slot-states", OrganizerSlotStateViewSet)  # CRUD pro stavy pozic v organizéru


# URL patterns - Všechny registrované routes z routeru
urlpatterns = [
    # Zahrnuje všechny automaticky generované routes z DefaultRouter
    # Např. /api/operators/ (list), /api/operators/{id}/ (detail), atd.
    path("", include(router.urls)),
]

