from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .permissions import ManagementOnly, ManagementOrService, OperatorsCanWrite
from django.utils import timezone

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
    AssemblyTypeDetailSerializer
)


class OperatorRoleViewSet(viewsets.ModelViewSet):
    queryset = OperatorRole.objects.all()
    serializer_class = OperatorRoleSerializer


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer


class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    permission_classes = [ManagementOrService]


class BinViewSet(viewsets.ModelViewSet):
    queryset = Bin.objects.all()
    serializer_class = BinSerializer
    permission_classes = [ManagementOrService]


class AssemblyComponentViewSet(viewsets.ModelViewSet):
    queryset = AssemblyComponent.objects.all()
    serializer_class = AssemblyComponentSerializer
    permission_classes = [ManagementOrService]


class AssemblyStepViewSet(viewsets.ModelViewSet):
    queryset = AssemblyStep.objects.all()
    serializer_class = AssemblyStepSerializer
    permission_classes = [ManagementOrService]


class StepRequiredComponentViewSet(viewsets.ModelViewSet):
    queryset = StepRequiredComponent.objects.all()
    serializer_class = StepRequiredComponentSerializer


class EventLogViewSet(viewsets.ModelViewSet):
    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer


class StepObjectViewSet(viewsets.ModelViewSet):
    queryset = StepObject.objects.all()
    serializer_class = StepObjectSerializer


class StepExecutionViewSet(viewsets.ModelViewSet):
    queryset = StepExecution.objects.all()
    serializer_class = StepExecutionSerializer
    # permission_classes = [...]  # later, when needed

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        Mark a step execution as completed (set end_time + is_completed).
        """
        step_exec = self.get_object()

        if step_exec.is_completed:
            return Response(
                {"detail": "Step execution is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        step_exec.end_time = timezone.now()
        step_exec.is_completed = True
        step_exec.save()

        serializer = self.get_serializer(step_exec)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ErrorTypeViewSet(viewsets.ModelViewSet):
    queryset = ErrorType.objects.all()
    serializer_class = ErrorTypeSerializer


class ErrorLogViewSet(viewsets.ModelViewSet):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer

class AssemblyTypeViewSet(viewsets.ModelViewSet):
    queryset = AssemblyType.objects.all()
    serializer_class = AssemblyTypeSerializer
    permission_classes = [ManagementOrService]

    @action(detail=True, methods=["get"])
    def detail_full(self, request, pk=None):
        assembly = self.get_object()
        serializer = AssemblyTypeDetailSerializer(assembly)
        return Response(serializer.data)

    
class AssemblyExecutionViewSet(viewsets.ModelViewSet):
    queryset = AssemblyExecution.objects.all()
    serializer_class = AssemblyExecutionSerializer
    # permission_classes = [...]  # later, when you want roles

    @action(detail=False, methods=["post"])
    def start(self, request):
        """
        Start a new assembly execution for the logged-in operator.
        """
        assembly_type_id = request.data.get("assembly_type_id")
        if not assembly_type_id:
            return Response(
                {"detail": "assembly_type_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # get assembly type
        try:
            assembly_type = AssemblyType.objects.get(id=assembly_type_id)
        except AssemblyType.DoesNotExist:
            return Response(
                {"detail": "AssemblyType not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        operator = getattr(user, "operator_profile", None)
        if operator is None:
            return Response(
                {"detail": "Logged-in user is not linked to an Operator."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution = AssemblyExecution.objects.create(
            assembly_type=assembly_type,
            operator=operator,
            # start_time is auto_now_add
        )

        serializer = self.get_serializer(execution)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        Mark an assembly execution as completed (set end_time + is_completed).
        """
        execution = self.get_object()

        if execution.is_completed:
            return Response(
                {"detail": "Execution is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution.end_time = timezone.now()
        execution.is_completed = True
        execution.save()

        serializer = self.get_serializer(execution)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def start_step(self, request, pk=None):
        """
        Start a step execution for this assembly execution.
        Expects `step_id` in the body.
        """
        execution = self.get_object()
        step_id = request.data.get("step_id")

        if not step_id:
            return Response(
                {"detail": "step_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            step = AssemblyStep.objects.get(id=step_id)
        except AssemblyStep.DoesNotExist:
            return Response(
                {"detail": "AssemblyStep not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Safety check: step must belong to same AssemblyType
        if step.assembly_id != execution.assembly_type_id:
            return Response(
                {"detail": "Step does not belong to this assembly type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optional: check there is no other open step for this execution
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

        step_exec = StepExecution.objects.create(
            assembly_execution=execution,
            step=step,
            # start_time auto_now_add, is_completed False by default
        )

        serializer = StepExecutionSerializer(step_exec)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
