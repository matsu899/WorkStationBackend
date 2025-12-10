from rest_framework import serializers
from .models import (
    OperatorRole,
    Operator,
    Component,
    Bin,
    AssemblyType,
    AssemblyComponent,
    StepRequiredComponent,
    AssemblyStep,
    EventLog,
    StepObject,
    AssemblyExecution,
    StepExecution,
    ErrorType,
    ErrorLog,
    OperatorRoleAssignment,
)


# OperatorRole Serializers
class OperatorRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorRole
        fields = '__all__'

# OperatorRoleAssignment Serializers
class OperatorRoleAssignmentSerializer(serializers.ModelSerializer):
    operator = serializers.StringRelatedField(read_only=True)
    role = OperatorRoleSerializer(read_only=True)
    assigned_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OperatorRoleAssignment
        fields = ["id", "operator", "role", "assigned_at", "assigned_by", "is_active"]

# Operator Serializers
class OperatorSerializer(serializers.ModelSerializer):
    # Read-only nested roles for GET
    roles = OperatorRoleSerializer(read_only=True, many=True)

    # Write-only list of role IDs for POST/PUT/PATCH
    role_ids = serializers.PrimaryKeyRelatedField(
        queryset=OperatorRole.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Operator
        fields = ["id", "name", "employee_id", "roles", "role_ids"]

    def _get_assigned_by_operator(self):
        """
        Helper to guess who is assigning the role.
        You’ll improve this later when you connect Django auth <-> Operator.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

    # use related_name from the Operator.user field
        return getattr(request.user, "operator_profile", None)

    def create(self, validated_data):
        role_ids = validated_data.pop("role_ids", [])
        operator = Operator.objects.create(**validated_data)

        assigned_by = self._get_assigned_by_operator()

        for role in role_ids:
            OperatorRoleAssignment.objects.create(
                operator=operator,
                role=role,
                assigned_by=assigned_by,
                is_active=True,
            )

        return operator

    def update(self, instance, validated_data):
        role_ids = validated_data.pop("role_ids", None)

        # update basic fields
        instance.name = validated_data.get("name", instance.name)
        instance.employee_id = validated_data.get("employee_id", instance.employee_id)
        instance.save()

        if role_ids is not None:
            assigned_by = self._get_assigned_by_operator()

            # deactivate old assignments
            OperatorRoleAssignment.objects.filter(
                operator=instance, is_active=True
            ).update(is_active=False)

            # create new assignments
            for role in role_ids:
                OperatorRoleAssignment.objects.create(
                    operator=instance,
                    role=role,
                    assigned_by=assigned_by,
                    is_active=True,
                )

        return instance

# Component Serializers
class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = "__all__"

# Bin Serializers
class BinSerializer(serializers.ModelSerializer):
    component = ComponentSerializer(read_only=True)
    component_id = serializers.PrimaryKeyRelatedField(
        queryset=Component.objects.all(),
        source="component",
        write_only=True
    )

    class Meta:
        model = Bin
        fields = ["id", "component", "component_id", "box_code", "location"]

# AssemblyType Serializers
class AssemblyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyType
        fields = "__all__"

# AssemblyComponent Serializers
class AssemblyComponentSerializer(serializers.ModelSerializer):
    component = ComponentSerializer(read_only=True)
    component_id = serializers.PrimaryKeyRelatedField(
        queryset=Component.objects.all(),
        source="component",
        write_only=True
    )

    assembly_type = AssemblyTypeSerializer(read_only=True)
    assembly_type_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyType.objects.all(),
        source="assembly_type",
        write_only=True
    )

    class Meta:
        model = AssemblyComponent
        fields = [
            "id",
            "assembly_type", "assembly_type_id",
            "component", "component_id",
            "quantity_required",
        ]

# EventLog Serializers
class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = "__all__"

# StepObject Serializers
class StepObjectSerializer(serializers.ModelSerializer):
    step_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyStep.objects.all(),
        source="step",
        write_only=True,
    )
    step = serializers.StringRelatedField(read_only=True)  # "Assembly X — Step 1"

    class Meta:
        model = StepObject
        fields = [
            "id",
            "step",
            "step_id",         
            "object_type",
            "position_x",
            "position_y",
            "width",
            "height",
            "z_index",
            "text_content",
            "image_path",
            "font_size",
        ]

    def validate(self, attrs):
        # support partial updates (PATCH)
        instance = getattr(self, "instance", None)

        object_type = attrs.get("object_type") or getattr(instance, "object_type", None)
        text = attrs.get("text_content", getattr(instance, "text_content", "") or "")
        image = attrs.get("image_path", getattr(instance, "image_path", "") or "")

        if object_type == StepObject.OBJECT_TYPE_TEXT:
            if not text.strip():
                raise serializers.ValidationError(
                    "For object_type='text', text_content must be non-empty."
                )
            # optionally auto-clear irrelevant field:
            attrs["image_path"] = ""

        elif object_type == StepObject.OBJECT_TYPE_IMAGE:
            if not image.strip():
                raise serializers.ValidationError(
                    "For object_type='image', image_path must be non-empty."
                )
            # optionally auto-clear irrelevant field:
            attrs["text_content"] = ""

        return attrs


# AssemblyExecution Serializers
class AssemblyExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyExecution
        fields = "__all__"

# StepExecution Serializers
class StepExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepExecution
        fields = "__all__"

# ErrorType Serializers
class ErrorTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorType
        fields = "__all__"

# ErrorLog Serializers
class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorLog
        fields = "__all__"

# StepRequiredComponent Serializers
class StepRequiredComponentSerializer(serializers.ModelSerializer):
    # Explicit read-only field for displaying the step (FK)
    step = serializers.PrimaryKeyRelatedField(read_only=True)

    # Write-only field used in POST/PUT/PATCH payloads
    step_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyStep.objects.all(),
        source="step",
        write_only=True,
    )

    component = ComponentSerializer(read_only=True)
    component_id = serializers.PrimaryKeyRelatedField(
        queryset=Component.objects.all(),
        source="component",
        write_only=True,
    )

    bin = BinSerializer(read_only=True)
    bin_id = serializers.PrimaryKeyRelatedField(
        queryset=Bin.objects.all(),
        source="bin",
        write_only=True,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = StepRequiredComponent
        fields = [
            "id",
            "step", "step_id",
            "component", "component_id",
            "bin", "bin_id",
            "quantity",
        ]



# AssemblyStep Serializers
class AssemblyStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyStep
        fields = "__all__"

    def validate_order(self, value):
        if value <= 0:
            raise serializers.ValidationError("Order must be a positive number (1, 2, 3, ...).")
        return value

# Detailed AssemblyStep Serializer
class AssemblyStepDetailSerializer(serializers.ModelSerializer):
    required_components = StepRequiredComponentSerializer(
        source="steprequiredcomponent_set",
        many=True,
        read_only=True
    )
    step_objects = StepObjectSerializer(
        source="stepobject_set",
        many=True,
        read_only=True
    )

    class Meta:
        model = AssemblyStep
        fields = [
            "id",
            "assembly",
            "order",
            "title",
            "description",
            "required_components",
            "step_objects",
        ]

class StepRequiredComponentNestedSerializer(serializers.ModelSerializer):
    component = ComponentSerializer(read_only=True)
    bin = BinSerializer(read_only=True)

    class Meta:
        model = StepRequiredComponent
        fields = [
            "id",
            "component",
            "bin",
            "quantity",
        ]


class StepObjectNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepObject
        fields = [
            "id",
            "object_type",
            "position_x",
            "position_y",
            "width",
            "height",
            "z_index",
            "text_content",
            "image_path",
        ] 

class AssemblyTypeDetailSerializer(serializers.ModelSerializer):
    steps = AssemblyStepDetailSerializer(
        many=True,
        source="assemblystep_set",
        read_only=True,
    )

    class Meta:
        model = AssemblyType
        fields = [
            "id",
            "name",
            "description",
            "version",
            "is_active",
            "image_path",
            "steps",
        ]