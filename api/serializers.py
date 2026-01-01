"""
Serializery pro Django REST Framework
Převádí Django modely na JSON a zpět pro API komunikaci
"""

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
    OrganizerSlotState,
)

# =============================================================================
# OPERÁTOR A ROLE - SERIALIZERY
# =============================================================================

# Serializer pro roli operátora
class OperatorRoleSerializer(serializers.ModelSerializer):
    # Vrací všechna pole modelu
    class Meta:
        model = OperatorRole
        fields = '__all__'

# Serializer pro přiřazení role operátorovi
class OperatorRoleAssignmentSerializer(serializers.ModelSerializer):
    # Pouze čtení - vrátí string reprezentaci operátora
    operator = serializers.StringRelatedField(read_only=True)
    # Vrátí kompletní data role
    role = OperatorRoleSerializer(read_only=True)
    # Pouze čtení - kdo roli přiřadil
    assigned_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OperatorRoleAssignment
        fields = ["id", "operator", "role", "assigned_at", "assigned_by", "is_active"]

# Serializer pro operátora s podporou rolí
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
        Pomocná funkce pro určení, kdo roli přiřazuje.
        Připojuje Django uživatele k Operátor profilu.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        # Použije related_name z pole Operator.user
        return getattr(request.user, "operator_profile", None)

    def create(self, validated_data):
        # Extrakt ID rolí z dat
        role_ids = validated_data.pop("role_ids", [])
        # Vytvoří operátora
        operator = Operator.objects.create(**validated_data)

        # Zjistí, kdo přiřazuje roli
        assigned_by = self._get_assigned_by_operator()

        # Přiřadí jednotlivé role
        for role in role_ids:
            OperatorRoleAssignment.objects.create(
                operator=operator,
                role=role,
                assigned_by=assigned_by,
                is_active=True,
            )

        return operator

    def update(self, instance, validated_data):
        # Extrakt ID rolí (může být None = bez změny)
        role_ids = validated_data.pop("role_ids", None)

        # Aktualizuje základní pole
        instance.name = validated_data.get("name", instance.name)
        instance.employee_id = validated_data.get("employee_id", instance.employee_id)
        instance.save()

        if role_ids is not None:
            assigned_by = self._get_assigned_by_operator()

            # Deaktivuje staré přiřazení rolí
            OperatorRoleAssignment.objects.filter(
                operator=instance, is_active=True
            ).update(is_active=False)

            # Vytvoří nová přiřazení
            for role in role_ids:
                OperatorRoleAssignment.objects.create(
                    operator=instance,
                    role=role,
                    assigned_by=assigned_by,
                    is_active=True,
                )

        return instance

# =============================================================================
# KOMPONENTY A ZÁSOBNÍKY - SERIALIZERY
# =============================================================================

# Serializer pro komponentu (součást)
class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        # Vrací všechna pole kromě kódu, který je automaticky generován
        fields = ["id", "component_code", "name", "description", "unit", "image_path"]
        # Tato pole nelze upravovat
        read_only_fields = ["id", "component_code"]

# Serializer pro zásobník
class BinSerializer(serializers.ModelSerializer):
    # Při GET: vrací kompletní data komponenty
    component = ComponentSerializer(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID komponenty
    component_id = serializers.PrimaryKeyRelatedField(
        source="component", queryset=Component.objects.all(), write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Bin
        fields = ["id", "bin_code", "component", "component_id"]
        # Tato pole nelze upravovat
        read_only_fields = ["id", "bin_code"]

# =============================================================================
# TYPY SESTAV A JEJICH KOMPONENTY - SERIALIZERY
# =============================================================================

# Serializer pro typ sestavy
class AssemblyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyType
        fields = "__all__"  # Vrací všechna pole

# Serializer pro komponentu v rámci typu sestavy
class AssemblyComponentSerializer(serializers.ModelSerializer):
    # Při GET: vrací kompletní data komponenty
    component = ComponentSerializer(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID komponenty
    component_id = serializers.PrimaryKeyRelatedField(
        queryset=Component.objects.all(),
        source="component",
        write_only=True
    )

    # Při GET: vrací kompletní data typu sestavy
    assembly_type = AssemblyTypeSerializer(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID typu sestavy
    assembly_type_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyType.objects.all(),
        source="assembly_type",
        write_only=True
    )

    class Meta:
        model = AssemblyComponent
        fields = [
            "id",
            "assembly_type", "assembly_type_id",  # Typ sestavy
            "component", "component_id",  # Komponenta
            "quantity_required",  # Požadované množství
        ]

# =============================================================================
# PROTOKOLY UDÁLOSTÍ A CHYB - SERIALIZERY
# =============================================================================

# Serializer pro protokol událostí
class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = "__all__"  # Vrací všechna pole

# =============================================================================
# OBJEKTY KROKỦ A KOMPONENTY KROKŮ - SERIALIZERY
# =============================================================================

# Serializer pro objekty (text/obrázek) v kroku montáže
class StepObjectSerializer(serializers.ModelSerializer):
    # Při POST/PUT/PATCH: přijímá ID kroku
    step_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyStep.objects.all(),
        source="step",
        write_only=True,
    )
    # Při GET: vrací string reprezentaci kroku (např. "Assembly X — Step 1")
    step = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StepObject
        fields = [
            "id",
            "step",
            "step_id",  # ID kroku pro zápis
            "object_type",  # TYP: text nebo image
            "position_x",  # Pozice X
            "position_y",  # Pozice Y
            "width",  # Šířka
            "height",  # Výška
            "z_index",  # Vrstva (pořadí překrytí)
            "text_content",  # Text (pro typ text)
            "image_path",  # Cesta k obrázku (pro typ image)
            "font_size",  # Velikost písma
        ]

    def validate(self, attrs):
        # Podporuje částečné aktualizace (PATCH)
        instance = getattr(self, "instance", None)

        # Zjistí typ objektu
        object_type = attrs.get("object_type") or getattr(instance, "object_type", None)
        text = attrs.get("text_content", getattr(instance, "text_content", "") or "")
        image = attrs.get("image_path", getattr(instance, "image_path", "") or "")

        # Validace pro textové objekty
        if object_type == StepObject.OBJECT_TYPE_TEXT:
            if not text.strip():
                raise serializers.ValidationError(
                    "For object_type='text', text_content must be non-empty."
                )
            # Smaže prázdný obrázek
            attrs["image_path"] = ""

        # Validace pro objekty s obrázky
        elif object_type == StepObject.OBJECT_TYPE_IMAGE:
            if not image.strip():
                raise serializers.ValidationError(
                    "For object_type='image', image_path must be non-empty."
                )
            # Smaže prázdný text
            attrs["text_content"] = ""

        return attrs


# =============================================================================
# PROVÁDĚNÍ MONTÁŽE - SERIALIZERY
# =============================================================================

# Serializer pro provádění montáže
class AssemblyExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyExecution
        fields = "__all__"

# Serializer pro provádění kroku
class StepExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepExecution
        fields = "__all__"

# =============================================================================
# CHYBY - SERIALIZERY
# =============================================================================

# Serializer pro typ chyby
class ErrorTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorType
        fields = "__all__"

# Serializer pro protokol chyb
class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorLog
        fields = "__all__"

# Serializer pro komponentu požadovanou v kroku (alternativní)
class StepRequiredComponentSerializer(serializers.ModelSerializer):
    # Při GET: vrací ID kroku
    step = serializers.PrimaryKeyRelatedField(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID kroku
    step_id = serializers.PrimaryKeyRelatedField(
        queryset=AssemblyStep.objects.all(),
        source="step",
        write_only=True,
    )

    # Při GET: vrací kompletní data komponenty
    component = ComponentSerializer(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID komponenty
    component_id = serializers.PrimaryKeyRelatedField(
        queryset=Component.objects.all(),
        source="component",
        write_only=True,
    )

    # Při GET: vrací kompletní data preferovaných zásobníků
    preferred_bins = BinSerializer(many=True, read_only=True)
    # Při POST/PUT/PATCH: přijímá seznam ID preferovaných zásobníků
    preferred_bin_ids = serializers.PrimaryKeyRelatedField(
        source="preferred_bins",
        many=True,
        queryset=Bin.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = StepRequiredComponent
        fields = [
            "id",
            "step", "step_id",  # Krok
            "component", "component_id",  # Komponenta
            "quantity",  # Požadované množství
            "preferred_bins", "preferred_bin_ids",  # Preferované zásobníky
        ]

# =============================================================================
# KROKY MONTÁŽE - SERIALIZERY (ROZŠÍŘENÉ)
# =============================================================================

# Serializer pro krok montáže
class AssemblyStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssemblyStep
        fields = "__all__"

    def validate_order(self, value):
        # Kontroluje, že pořadí je kladné číslo
        if value <= 0:
            raise serializers.ValidationError("Order must be a positive number (1, 2, 3, ...).")
        return value

# Rozšířený serializer pro krok montáže s vnořenými daty
class AssemblyStepDetailSerializer(serializers.ModelSerializer):
    # Vrací všechny komponenty požadované v tomto kroku
    required_components = StepRequiredComponentSerializer(
        many=True,
        read_only=True
    )
    # Vrací všechny objekty (text/obrázky) v tomto kroku
    step_objects = StepObjectSerializer(
        source="stepobject_set",  # Zpětný vztah k StepObject
        many=True,
        read_only=True
    )

    class Meta:
        model = AssemblyStep
        fields = [
            "id",
            "assembly",  # Typ sestavy
            "order",  # Pořadí kroku
            "title",  # Název
            "description",  # Popis
            "required_components",  # Požadované komponenty
            "step_objects",  # Objekty v kroku
        ]


# Vnořený serializer pro komponentu požadovanou v kroku (zjednodušená verze)
class StepRequiredComponentNestedSerializer(serializers.ModelSerializer):
    # Vrací kompletní data komponenty
    component = ComponentSerializer(read_only=True)
    # Vrací kompletní data preferovaných zásobníků
    preferred_bins = BinSerializer(many=True, read_only=True)

    class Meta:
        model = StepRequiredComponent
        fields = [
            "id",
            "component",  # Komponenta
            "quantity",  # Požadované množství
            "preferred_bins",  # Preferované zásobníky
        ]


# Vnořený serializer pro objekty v kroku (zjednodušená verze)
class StepObjectNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepObject
        fields = [
            "id",
            "object_type",  # TYP: text nebo image
            "position_x",  # Pozice X
            "position_y",  # Pozice Y
            "width",  # Šířka
            "height",  # Výška
            "z_index",  # Vrstva
            "text_content",  # Text
            "image_path",  # Cesta k obrázku
        ] 

# =============================================================================
# DETAILNÍ SERIALIZERY PRO KOMPLEXNÍ STRUKTURY
# =============================================================================

# Rozšířený serializer pro typ sestavy s kompletními daty
class AssemblyTypeDetailSerializer(serializers.ModelSerializer):
    # Vrací všechny kroky v tomto typu sestavy
    steps = AssemblyStepDetailSerializer(
        many=True,
        source="assemblystep_set",  # Zpětný vztah k AssemblyStep
        read_only=True,
    )

    class Meta:
        model = AssemblyType
        fields = [
            "id",
            "name",  # Název
            "description",  # Popis
            "version",  # Verze
            "is_active",  # Je aktivní?
            "image_path",  # Obrázek
            "steps",  # Kroky montáže
        ]

# =============================================================================
# ORGANIZÉR - SERIALIZERY
# =============================================================================

# Serializer pro stav pozice v organizéru
class OrganizerSlotStateSerializer(serializers.ModelSerializer):
    # Při GET: vrací kompletní data zásobníku
    bin = BinSerializer(read_only=True)
    # Při POST/PUT/PATCH: přijímá ID zásobníku
    bin_id = serializers.PrimaryKeyRelatedField(
        source="bin", queryset=Bin.objects.all(), write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = OrganizerSlotState
        fields = [
            "id",
            "organizer",  # Organizér
            "position",  # Pozice
            "bin",  # Zásobník (GET)
            "bin_id",  # ID zásobníku (POST/PUT/PATCH)
            "is_present",  # Je zásobník přítomen?
            "is_empty",  # Je prázdný? (dle vize)
            "last_seen",  # Poslední kontrola
            "session_id",  # ID relace
        ]
        read_only_fields = ["id"]

# =============================================================================
# POKROČILÉ SERIALIZERY PRO VEDENÍ OPERÁTORA
# =============================================================================

# Serializer pro komponentu v kroku s informacemi o pozicích (pro vedení)
class StepRequiredComponentGuidanceSerializer(StepRequiredComponentSerializer):
    # Vrací seznam všech pozic v organizéru, které obsahují tuto komponentu
    valid_positions = serializers.SerializerMethodField()
    # Vrací seznam preferovaných pozic v organizéru pro tuto komponentu
    preferred_positions = serializers.SerializerMethodField()

    def _latest_session_id(self, organizer_id: int):
        """Zjistí poslední ID relace v organizéru"""
        return (OrganizerSlotState.objects
                .filter(organizer_id=organizer_id)
                .order_by("-last_seen")
                .values_list("session_id", flat=True)
                .first())

    def get_valid_positions(self, obj):
        """Najde všechny pozice s danou komponentou"""
        organizer_id = self.context.get("organizer_id")
        if not organizer_id:
            return []

        # Využije poslední ID relace, pokud není specifikováno
        session_id = self.context.get("session_id") or self._latest_session_id(organizer_id)
        if not session_id:
            return []

        # Hledá všechny přítomné zásobníky s danou komponentou
        qs = OrganizerSlotState.objects.filter(
            organizer_id=organizer_id,
            session_id=session_id,
            is_present=True,
            bin__component=obj.component
        ).values_list("position", flat=True)

        return list(qs)

    def get_preferred_positions(self, obj):
        """Najde všechny preferované pozice s danou komponentou"""
        organizer_id = self.context.get("organizer_id")
        if not organizer_id:
            return []

        # Využije poslední ID relace, pokud není specifikováno
        session_id = self.context.get("session_id") or self._latest_session_id(organizer_id)
        if not session_id:
            return []

        # Zkontroluje, zda jsou preferované zásobníky nastaveny
        if not hasattr(obj, "preferred_bins"):
            return []

        # Hledá pozice v organizéru s preferovanými zásobníky
        qs = OrganizerSlotState.objects.filter(
            organizer_id=organizer_id,
            session_id=session_id,
            is_present=True,
            bin__in=obj.preferred_bins.all()
        ).values_list("position", flat=True)

        return list(qs)
