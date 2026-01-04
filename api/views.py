"""
Pohledy (ViewSets) pro Django REST Framework
Definuje API endpointy pro manipulaci s daty a obchodní logiku
"""

from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .permissions import ManagementOnly, ManagementOrService, OperatorsCanWrite
from django.utils import timezone
from rest_framework.request import Request
from typing import Optional
import uuid

from .models import (
    OperatorRole,
    Operator,
    Component,
    Bin,
    AssemblyType,
    AssemblyComponent,
    AssemblyStep,
    StepRequiredComponent,
    EventLog,
    StepObject,
    AssemblyExecution,
    StepExecution,
    ErrorType,
    ErrorLog,
    OrganizerSlotState,
    Organizer,
)
from .serializers import (
    OperatorRoleSerializer,
    OperatorSerializer,
    ComponentSerializer,
    BinSerializer,
    AssemblyTypeSerializer,
    AssemblyComponentSerializer,
    AssemblyStepSerializer,
    StepRequiredComponentSerializer,
    EventLogSerializer,
    StepObjectSerializer,
    AssemblyExecutionSerializer,
    StepExecutionSerializer,
    ErrorTypeSerializer,
    ErrorLogSerializer,
    AssemblyTypeDetailSerializer,
    OrganizerSlotStateSerializer,
)

# =============================================================================
# OPERÁTOR A ROLE - VIEWSETY
# =============================================================================

# ViewSet pro roli operátora - Standardní CRUD operace
class OperatorRoleViewSet(viewsets.ModelViewSet):
    queryset = OperatorRole.objects.all()
    serializer_class = OperatorRoleSerializer


# ViewSet pro operátora - Standardní CRUD operace
class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer

# =============================================================================
# KOMPONENTY A ZÁSOBNÍKY - VIEWSETY
# =============================================================================

# ViewSet pro komponentu - CRUD operace jen pro management
class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    permission_classes = [ManagementOrService]  # Jen management a service mohou spravovat


# ViewSet pro zásobník - CRUD operace jen pro management
class BinViewSet(viewsets.ModelViewSet):
    queryset = Bin.objects.all()
    serializer_class = BinSerializer
    permission_classes = [ManagementOrService]

    def get_queryset(self):
        qs = super().get_queryset()
        code = self.request.query_params.get("bin_code")
        if code:
            qs = qs.filter(bin_code=code)
        return qs


# =============================================================================
# TYPY SESTAV - VIEWSETY
# =============================================================================

# ViewSet pro komponentu v rámci typu sestavy
class AssemblyComponentViewSet(viewsets.ModelViewSet):
    queryset = AssemblyComponent.objects.all()
    serializer_class = AssemblyComponentSerializer
    permission_classes = [ManagementOrService]  # Jen management a service mohou spravovat


# ViewSet pro typ sestavy
class AssemblyTypeViewSet(viewsets.ModelViewSet):
    queryset = AssemblyType.objects.all()
    serializer_class = AssemblyTypeSerializer
    permission_classes = [ManagementOrService]  # Jen management a service mohou spravovat

    @action(detail=True, methods=["get"])
    def detail_full(self, request, pk=None):
        """
        GET /assembly-types/{id}/detail_full/
        Vrací kompletní data typu sestavy s vnořenými kroky a jejich objekty.
        """
        assembly = self.get_object()
        serializer = AssemblyTypeDetailSerializer(assembly)
        return Response(serializer.data)

# =============================================================================
# KROKY MONTÁŽE - VIEWSETY
# =============================================================================

# ViewSet pro krok montáže
class AssemblyStepViewSet(viewsets.ModelViewSet):
    queryset = AssemblyStep.objects.all()
    serializer_class = AssemblyStepSerializer
    permission_classes = [ManagementOrService]  # Jen management a service mohou spravovat

    @action(detail=True, methods=["get"])
    def guidance (self, request: Request, pk: Optional[str] = None):
        """
        GET /assembly-steps/{id}/guidance/?organizer_id=1&session_id=optional
        
        Vrací požadované komponenty v kroku s informací o tom, kde se nacházejí v organizéru.
        Pomáhá operátorovi najít správné komponenty v uzavřeném skladiště.
        
        Parametry:
        - organizer_id (povinný): ID organizéru (skladiště)
        - session_id (volitelný): ID relace skenování; pokud není, vezme poslední
        
        Odpověď obsahuje:
        - step_id: ID kroku
        - organizer_id: ID organizéru
        - session_id: ID relace
        - requirements: Seznam požadovaných komponent s pozicemi, kde se nacházejí
        """
        step = self.get_object()
        organizer_id = request.query_params.get("organizer_id") or request.query_params.get("organizer")
        if not organizer_id:
            return Response({"detail": "organizer_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        session_id = request.query_params.get("session_id")

        if not session_id:
            # Pokud není specifikovaná relace, vezme poslední
            latest_row = (OrganizerSlotState.objects
                          .filter(organizer_id=organizer_id)
                          .exclude(last_seen__isnull=True)
                          .order_by("-last_seen")
                          .first())
            session_id = latest_row.session_id if latest_row else None

        # Načte všechny komponenty požadované v tomto kroku
        reqs = step.required_components.select_related("component").all()

        result = []
        for req in reqs:
            valid_positions = []
            if session_id:
                # Najde pozice v organizéru, které obsahují tuto komponentu
                valid_positions = list(
                    OrganizerSlotState.objects.filter(
                        organizer_id=organizer_id,
                        session_id=session_id,
                        is_present=True,
                        bin__component=req.component,
                    ).values_list("position", flat=True)
                )

            result.append({
                "id": req.id,
                "component": ComponentSerializer(req.component).data,
                "quantity": req.quantity,
                "valid_positions": valid_positions,  # Pozice v organizéru, kde je komponenta
            })

        return Response(
            {
                "step_id": step.id,
                "organizer_id": int(organizer_id),
                "session_id": str(session_id) if session_id else None,
                "requirements": result,
            },
            status=status.HTTP_200_OK,
        )

# ViewSet pro komponentu požadovanou v kroku
class StepRequiredComponentViewSet(viewsets.ModelViewSet):
    queryset = StepRequiredComponent.objects.all()
    serializer_class = StepRequiredComponentSerializer

# =============================================================================
# OBJEKTY V KROCÍCH - VIEWSETY
# =============================================================================

# ViewSet pro objekty (text/obrázky) v krocích montáže
class StepObjectViewSet(viewsets.ModelViewSet):
    queryset = StepObject.objects.all()
    serializer_class = StepObjectSerializer

# =============================================================================
# LOGOVÁNÍ UDÁLOSTÍ A CHYB - VIEWSETY
# =============================================================================

# ViewSet pro protokol událostí
class EventLogViewSet(viewsets.ModelViewSet):
    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer


# ViewSet pro typ chyby
class ErrorTypeViewSet(viewsets.ModelViewSet):
    queryset = ErrorType.objects.all()
    serializer_class = ErrorTypeSerializer


# ViewSet pro protokol chyb
class ErrorLogViewSet(viewsets.ModelViewSet):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer

# =============================================================================
# PROVÁDĚNÍ MONTÁŽE - VIEWSETY
# =============================================================================

# ViewSet pro provádění kroku montáže
class StepExecutionViewSet(viewsets.ModelViewSet):
    queryset = StepExecution.objects.all()
    serializer_class = StepExecutionSerializer
    # permission_classes = [...]  # Později bude nutné nastavit dle rolí

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        POST /step-executions/{id}/complete/
        
        Označí provádění kroku jako hotové.
        Nastaví čas ukončení a příznak je_hotovo.
        """
        step_exec = self.get_object()

        # Kontrola, že krok není již hotov
        if step_exec.is_completed:
            return Response(
                {"detail": "Step execution is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Označí krok jako hotový
        step_exec.end_time = timezone.now()
        step_exec.is_completed = True
        step_exec.save()

        serializer = self.get_serializer(step_exec)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ViewSet pro provádění montáže
class AssemblyExecutionViewSet(viewsets.ModelViewSet):
    queryset = AssemblyExecution.objects.all()
    serializer_class = AssemblyExecutionSerializer
    # permission_classes = [...]  # Později bude nutné nastavit dle rolí

    @action(detail=False, methods=["post"])
    def start(self, request):
        """
        POST /assembly-executions/start/
        
        Spustí novou montáž pro přihlášeného operátora.
        Vyžaduje assembly_type_id v těle požadavku.
        """
        assembly_type_id = request.data.get("assembly_type_id")
        if not assembly_type_id:
            return Response(
                {"detail": "assembly_type_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Najde typ sestavy
        try:
            assembly_type = AssemblyType.objects.get(id=assembly_type_id)
        except AssemblyType.DoesNotExist:
            return Response(
                {"detail": "AssemblyType not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Najde operátora přihlášeného uživatele
        user = request.user
        operator = getattr(user, "operator_profile", None)
        if operator is None:
            return Response(
                {"detail": "Logged-in user is not linked to an Operator."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vytvoří nový záznam o montáži
        execution = AssemblyExecution.objects.create(
            assembly_type=assembly_type,
            operator=operator,
            # start_time se nastaví automaticky
        )

        serializer = self.get_serializer(execution)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        POST /assembly-executions/{id}/complete/
        
        Označí montáž jako hotovou.
        Nastaví čas ukončení a příznak je_hotovo.
        """
        execution = self.get_object()

        # Kontrola, že montáž není již hotova
        if execution.is_completed:
            return Response(
                {"detail": "Execution is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Označí montáž jako hotovou
        execution.end_time = timezone.now()
        execution.is_completed = True
        execution.save()

        serializer = self.get_serializer(execution)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def start_step(self, request, pk=None):
        """
        POST /assembly-executions/{id}/start_step/
        
        Spustí provádění kroku v rámci montáže.
        Vyžaduje step_id v těle požadavku.
        """
        execution = self.get_object()
        step_id = request.data.get("step_id")

        if not step_id:
            return Response(
                {"detail": "step_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Najde krok
        try:
            step = AssemblyStep.objects.get(id=step_id)
        except AssemblyStep.DoesNotExist:
            return Response(
                {"detail": "AssemblyStep not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Bezpečnostní kontrola: krok musí patřit stejnému typu sestavy
        if step.assembly_id != execution.assembly_type_id:
            return Response(
                {"detail": "Step does not belong to this assembly type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Volitelně: kontrola, že není již otevřený jiný krok
        open_steps = StepExecution.objects.filter(
            assembly_execution=execution, is_completed=False
        )
        if open_steps.exists():
            return Response(
                {
                    "detail": "There is already an open step execution.",
                    "open_step_ids": list(open_steps.values_list("id", flat=True)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vytvoří nový záznam o provádění kroku
        step_exec = StepExecution.objects.create(
            assembly_execution=execution,
            step=step,
            # start_time se nastaví automaticky, is_completed je standardně False
        )

        serializer = StepExecutionSerializer(step_exec)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# =============================================================================
# ORGANIZÉR (SKLADIŠTĚ) - VIEWSETY
# =============================================================================

# ViewSet pro stavy pozic v organizéru
class OrganizerSlotStateViewSet(viewsets.ModelViewSet):
    queryset = OrganizerSlotState.objects.all()
    serializer_class = OrganizerSlotStateSerializer
    permission_classes = [ManagementOrService]  # Typicky kamera a GUI služba

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """
        GET /organizer-slot-states/latest/?organizer_id=1
        
        Vrací nejnovější stav všech pozic v organizéru.
        Vrací: ID poslední relace skenování + všechny pozice z té relace.
        """
        organizer_id = request.query_params.get("organizer_id")
        if not organizer_id:
            return Response({"detail": "organizer_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Najde poslední relaci: priorita last_seen, fallback na session_id
        latest_row = (OrganizerSlotState.objects
                      .filter(organizer_id=organizer_id)
                      .exclude(last_seen__isnull=True)
                      .order_by("-last_seen")
                      .first())

        if not latest_row:
            # Žádné skeny zatím
            return Response({"session_id": None, "slots": []}, status=status.HTTP_200_OK)

        session_id = latest_row.session_id
        # Vrátí všechny pozice z poslední relace
        qs = OrganizerSlotState.objects.filter(organizer_id=organizer_id, session_id=session_id).order_by("position")
        data = OrganizerSlotStateSerializer(qs, many=True).data
        return Response({"session_id": str(session_id), "slots": data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def scan(self, request):
        """
        POST /organizer-slot-states/scan/
        
        Kamera posílá kompletní snapshot stavu všech pozic v jednom požadavku.
        Aktualizuje nebo vytváří záznamy pro každou pozici.

        Příklad těla požadavku:
        {
          "organizer_id": 1,
          "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (volitelné)",
          "slots": [
            {
              "position": 0,
              "bin_id": 12,
              "is_present": true,
              "is_empty": false,
              "last_seen": "2025-01-01T12:00:00Z"
            },
            {
              "position": 1,
              "bin_id": null,
              "is_present": false,
              "is_empty": null,
              "last_seen": "2025-01-01T12:00:00Z"
            }
          ]
        }
        """
        organizer_id = request.data.get("organizer_id")
        slots = request.data.get("slots", [])
        if not organizer_id:
            return Response({"detail": "organizer_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(slots, list):
            return Response({"detail": "slots must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        # Generuje nové session_id, pokud není poskytnuto
        session_id = request.data.get("session_id") or str(uuid.uuid4())
        now = timezone.now()

        updated_positions = []

        # Procházím každou pozici v požadavku
        for item in slots:
            pos = item.get("position")
            if pos is None:
                continue

            bin_id = item.get("bin_id")
            is_present = bool(item.get("is_present", False))
            is_empty = item.get("is_empty", None)

            # Použije zadaný čas skenování, nebo aktuální čas
            last_seen = item.get("last_seen")
            last_seen = timezone.datetime.fromisoformat(last_seen.replace("Z", "+00:00")) if isinstance(last_seen, str) else now

            # Aktualizuje nebo vytvoří záznam o pozici
            obj, _created = OrganizerSlotState.objects.update_or_create(
                organizer_id=organizer_id,
                position=pos,
                defaults={
                    "bin_id": bin_id,
                    "is_present": is_present,
                    "is_empty": is_empty,
                    "last_seen": last_seen,
                    "session_id": session_id,
                },
            )
            updated_positions.append(obj.position)

        return Response(
            {"detail": "scan stored", "session_id": session_id, "updated_positions": sorted(updated_positions)},
            status=status.HTTP_200_OK,
        )
    def get_queryset(self):
        qs = super().get_queryset()

        organizer = self.request.query_params.get("organizer")
        position = self.request.query_params.get("position")
        session_id = self.request.query_params.get("session_id")

        if organizer is not None:
            qs = qs.filter(organizer_id=organizer)

        if position is not None:
            qs = qs.filter(position=position)

        if session_id is not None:
            qs = qs.filter(session_id=session_id)

        return qs
