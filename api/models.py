from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User 
from django.conf import settings
import uuid
from django.utils.crypto import get_random_string
import uuid

# =============================================================================
# OPERÁTOR A ROLE OPERÁTORA
# =============================================================================
# Definuje role, které mohou operátoři mít v systému a evidenci přiřazení rolí

class OperatorRole(models.Model):
    # Model reprezentující roli operátora (např. supervisora, technika, atd.)
    role_name = models.CharField(max_length=100, unique=True)  # Název role (unikátní)
    description = models.TextField(blank=True)  # Popis role

    def __str__(self):
        return self.role_name

# Model operátora - pracovníka v systému
class Operator(models.Model):
    # Odkaz na uživatele Django (může být prázdný)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operator_profile",
    )
    name = models.CharField(max_length=100)  # Jméno operátora
    employee_id = models.CharField(max_length=50, unique=True)  # ID zaměstnance

    # Propojení na role prostřednictvím zprostředkující tabulky
    roles = models.ManyToManyField(
        OperatorRole,
        through="OperatorRoleAssignment",
        through_fields=("operator", "role"),
        related_name="operators",
        blank=True,
    )

    def __str__(self):
        return self.name
    
# Model pro přiřazení rolí operátorům (podrobnosti o přiřazení role)
class OperatorRoleAssignment(models.Model):
    # Odkaz na operátora a jeho roli
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)  # Operátor
    role = models.ForeignKey(OperatorRole, on_delete=models.CASCADE)  # Role

    assigned_at = models.DateTimeField(auto_now_add=True)  # Čas přiřazení

    # Operátor, který roli přiřadil
    assigned_by = models.ForeignKey(
        Operator,
        null=True,
        blank=True,
        related_name="assigned_roles",
        on_delete=models.SET_NULL,
    )

    is_active = models.BooleanField(default=True)  # Je přiřazení aktivní?

    class Meta:
        unique_together = ("operator", "role")  # Jeden operátor nemůže mít stejnou roli 2x

    def __str__(self):
        return f"{self.operator} → {self.role} (active={self.is_active})"

# =============================================================================
# KOMPONENTY A ZÁSOBNÍKY (BIN)
# =============================================================================
# Definuje komponenty (součásti) a jejich skladování v zásobnících

def generate_component_code():
    """Generuje jedinečný kód pro komponentu ve formátu CMP-XXXXXXXXXX"""
    return f"CMP-{uuid.uuid4().hex[:10].upper()}"

class Component(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, default="pcs")

    component_code = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False
    )

    image_path = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        if not self.component_code:
            while True:
                code = generate_component_code()
                if not Component.objects.filter(component_code=code).exists():
                    self.component_code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.component_code})"


def generate_bin_code():
    """Generuje jedinečný kód pro zásobník ve formátu BIN-XXXXXXXXXX"""
    return f"BIN-{get_random_string(10).upper()}"

# Model zásobníku (BIN) - fyzický kontejner na součásti
class Bin(models.Model):
    bin_code = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,  # Automaticky generovaný kód
    )

    # Komponenta uložená v tomto zásobníku
    component = models.ForeignKey(
        Component,
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # Chránit smazání komponenty, pokud existuje v zásobníku
        related_name="bins"
    )

    def save(self, *args, **kwargs):
        if not self.bin_code:
            while True:
                code = generate_bin_code()
                if not Bin.objects.filter(bin_code=code).exists():
                    self.bin_code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bin_code} ({self.component.name if self.component else 'empty'})"


# =============================================================================
# TYPY SESTAV A JEJICH KOMPONENTY
# =============================================================================
# Definuje typy sestav, které se montují, a jaké komponenty obsahují

# Model typu sestavy (např. Motor, Podvozek, atd.)
class AssemblyType(models.Model):
    name = models.CharField(max_length=200)  # Název typu sestavy
    description = models.TextField(blank=True)  # Popis
    version = models.CharField(max_length=50, default="1.0")  # Verze
    is_active = models.BooleanField(default=True)  # Je typ aktivní?
    image_path = models.CharField(max_length=200, blank=True)  # Obrázek

    def __str__(self):
        return self.name

# Model komponent potřebných pro konkrétní typ sestavy
class AssemblyComponent(models.Model):
    assembly_type = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)  # Typ sestavy
    component = models.ForeignKey(Component, on_delete=models.CASCADE)  # Komponenta
    quantity_required = models.PositiveIntegerField(default=1)  # Požadované množství

    def __str__(self):
        return f"{self.assembly_type.name} - {self.component.name}"
    
# =============================================================================
# KROKI MONTÁŽE A JEJICH OBJEKTY
# =============================================================================
# Definuje jednotlivé kroky v procesu montáže a jejich vizuální prvky

# Model komponenty požadované v určitém kroku montáže
class StepRequiredComponent(models.Model):
    step = models.ForeignKey("AssemblyStep", on_delete=models.CASCADE, related_name="required_components")  # Krok
    component = models.ForeignKey("Component", on_delete=models.PROTECT, related_name="required_in_steps")  # Komponenta
    quantity = models.PositiveIntegerField(default=1)  # Požadované množství

    # Preferované zásobníky pro tuto komponentu v tomto kroku
    preferred_bins = models.ManyToManyField(
        "Bin",
        blank=True,
        related_name="preferred_for_requirements"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["step", "component"], name="uniq_step_component_requirement"),
        ]


# Model kroku montáže - jeden krok v procesu montáže
class AssemblyStep(models.Model):
    assembly = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)  # Typ sestavy
    order = models.PositiveIntegerField()  # Pořadí kroku
    title = models.CharField(max_length=200)  # Název kroku
    description = models.TextField(blank=True)  # Popis

    class Meta:
        ordering = ["order"]  # Řazení podle pořadí
        constraints = [
            models.UniqueConstraint(
                fields=["assembly", "order"],
                name="unique_step_order_per_assembly",  # V jedné sestavě je pořadí unikátní
            )
        ]

    def __str__(self):
        return f"{self.assembly.name} — Step {self.order}"


# Model objektu v kroku montáže (text nebo obrázek)
class StepObject(models.Model):
    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE)  # Krok
    
    # Typ objektu
    OBJECT_TYPE_TEXT = "text"
    OBJECT_TYPE_IMAGE = "image"

    object_type = models.CharField(
        max_length=20,
        choices=[
            (OBJECT_TYPE_TEXT, "Text"),
            (OBJECT_TYPE_IMAGE, "Image"),
        ]
    )
    
    # Pozice a velikost objektu na obrazovce
    position_x = models.FloatField()  # Souřadnice X
    position_y = models.FloatField()  # Souřadnice Y
    width = models.FloatField()  # Šířka
    height = models.FloatField()  # Výška
    z_index = models.IntegerField()  # Vrstva (pořadí překrytí)
    
    # Obsah objektu
    text_content = models.TextField(blank=True)  # Text (pokud je typ TEXT)
    image_path = models.CharField(max_length=200, blank=True)  # Cesta k obrázku (pokud je typ IMAGE)
    font_size = models.IntegerField(default=40)  # Velikost písma

    def clean(self):
        # Validace: textové objekty musí mít obsah, obrázkové musí mít cestu
        super().clean()
        if self.object_type == self.OBJECT_TYPE_TEXT:
            if not (self.text_content or "").strip():
                raise ValidationError("Text objects must have non-empty text_content.")
        elif self.object_type == self.OBJECT_TYPE_IMAGE:
            if not (self.image_path or "").strip():
                raise ValidationError("Image objects must have a non-empty image_path.")

    def __str__(self):
        return f"{self.object_type} for {self.step}"

# =============================================================================
# PROVÁDĚNÍ MONTÁŽE A ZAZNAMENÁVÁNÍ CHYB
# =============================================================================
# Definuje provádění sestav (spuštění montáže) a zaznamenávání chyb

# Model provádění sestav - Instance montáže
class AssemblyExecution(models.Model):
    assembly_type = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)  # Typ sestavy
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)  # Operátor, který montuje
    start_time = models.DateTimeField(auto_now_add=True)  # Čas spuštění
    end_time = models.DateTimeField(null=True, blank=True)  # Čas ukončení
    is_completed = models.BooleanField(default=False)  # Je montáž hotova?

    def __str__(self):
        return f"Execution of {self.assembly_type.name} by {self.operator.name}"
    
# Model provádění kroku - Instance jednoho kroku v montáži
class StepExecution(models.Model):
    assembly_execution = models.ForeignKey(AssemblyExecution, on_delete=models.CASCADE)  # Montáž
    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE)  # Krok
    start_time = models.DateTimeField(auto_now_add=True)  # Čas spuštění
    end_time = models.DateTimeField(null=True, blank=True)  # Čas ukončení
    is_completed = models.BooleanField(default=False)  # Je krok hotov?

    def __str__(self):
        return f"Step {self.step.order} of {self.assembly_execution}"
    
# Model typu chyby - Definuje možné typy chyb
class ErrorType(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Název typu chyby
    description = models.TextField(blank=True)  # Popis

    def __str__(self):
        return self.name


# Výčet typů událostí, které se zaznamenávají
class EventType(models.TextChoices):
    BREAK_START = "BREAK_START", "Break started"  # Začátek přestávky
    BREAK_END = "BREAK_END", "Break ended"  # Konec přestávky
    REPAIR_START = "REPAIR_START", "Repair started"  # Začátek opravy
    REPAIR_END = "REPAIR_END", "Repair ended"  # Konec opravy
    WAIT_START = "WAIT_START", "Waiting for material started"  # Čekání na materiál
    WAIT_END = "WAIT_END", "Waiting for material ended"  # Konec čekání

# Model protokolu událostí - Zaznamenávání všech důležitých událostí
class EventLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)  # Čas události

    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,  # Typ události
    )

    operator = models.ForeignKey(
        Operator,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # Operátor (pokud relevantní)
    )

    assembly_execution = models.ForeignKey(
        AssemblyExecution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # Montáž (pokud relevantní)
    )

    step_execution = models.ForeignKey(
        StepExecution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # Krok (pokud relevantní)
    )

    related_bin = models.ForeignKey(
        Bin,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # Zainteresovaný zásobník
    )

    notes = models.TextField(blank=True)  # Dodatečné poznámky

    class Meta:
        ordering = ["timestamp"]  # Řazení od nejstarší

    def __str__(self):
        return f"{self.timestamp} — {self.event_type}"

# Model protokolu chyb - Zaznamenávání chyb a problémů během montáže
class ErrorLog(models.Model):
    step_execution = models.ForeignKey(StepExecution, null=True, blank=True, on_delete=models.SET_NULL)  # Krok
    error_type = models.ForeignKey(ErrorType, on_delete=models.CASCADE)  # Typ chyby
    timestamp = models.DateTimeField(auto_now_add=True)  # Čas chyby
    notes = models.TextField(blank=True)  # Dodatečné poznámky

    class Meta:
        ordering = ["timestamp"]  # Řazení od nejstarší

    def __str__(self):
        return f"Error {self.error_type.name} at {self.timestamp}"
    
# =============================================================================
# ORGANIZÉR (SKLADIŠTĚ)
# =============================================================================
# Definuje fyzickou strukturu skladiště a stav jednotlivých pozic

# Model organizéru - Fyzický organizér (police, přepážka, atd.)
class Organizer(models.Model):
    name = models.CharField(max_length=120)  # Název organizéru

    def __str__(self):
        return self.name


# Model stavu jednotlivé pozice v organizéru
class OrganizerSlotState(models.Model):
    organizer = models.ForeignKey(
        Organizer,
        on_delete=models.CASCADE,
        related_name="slot_states"
    )
    position = models.PositiveIntegerField()
    bin = models.ForeignKey(
        Bin,
        null=True,
        blank=True,
        on_delete=models.PROTECT
    )
    is_present = models.BooleanField(default=False)

    is_empty = models.BooleanField(
        null=True,
        blank=True,
        help_text="None = unknown, True = empty, False = contains parts"
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    session_id = models.UUIDField(db_index=True, default=uuid.uuid4)

    led_section = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Physical LED/light-gate section number for this slot"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organizer", "position"],
                name="uniq_position_per_organizer"
            ),
            models.UniqueConstraint(
                fields=["organizer", "led_section"],
                name="uniq_led_section_per_organizer"
            ),
        ]