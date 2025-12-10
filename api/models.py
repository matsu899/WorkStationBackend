from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User 
from django.conf import settings



class OperatorRole(models.Model):
    role_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.role_name

class Operator(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operator_profile",
    )
    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)

    roles = models.ManyToManyField(
        OperatorRole,
        through="OperatorRoleAssignment",
        through_fields=("operator", "role"),
        related_name="operators",
        blank=True,
    )

    def __str__(self):
        return self.name
    
class OperatorRoleAssignment(models.Model):
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    role = models.ForeignKey(OperatorRole, on_delete=models.CASCADE)

    assigned_at = models.DateTimeField(auto_now_add=True)

    assigned_by = models.ForeignKey(
        Operator,
        null=True,
        blank=True,
        related_name="assigned_roles",
        on_delete=models.SET_NULL,
    )

    is_active = models.BooleanField(default=True)  

    class Meta:
        unique_together = ("operator", "role") 

    def __str__(self):
        return f"{self.operator} → {self.role} (active={self.is_active})"

class Component(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, default="pcs")
    component_code = models.CharField(max_length=100, unique=True,null=True, blank=True)
    image_path = models.CharField(max_length=200, blank=True)


class Bin(models.Model):
    box_code = models.CharField(max_length=100, unique=True) 

    
    component = models.ForeignKey(
        Component,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    location = models.CharField(max_length=100, blank=True) 

    def __str__(self):
        return f"Bin {self.id} ({self.component.name if self.component else 'empty'})"



class AssemblyType(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=50, default="1.0")
    is_active = models.BooleanField(default=True)
    image_path = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

class AssemblyComponent(models.Model):
    assembly_type = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)
    component = models.ForeignKey(Component, on_delete=models.CASCADE)
    quantity_required = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.assembly_type.name} - {self.component.name}"
    
class StepRequiredComponent(models.Model):
    step = models.ForeignKey("AssemblyStep", on_delete=models.CASCADE)
    component = models.ForeignKey("Component", on_delete=models.CASCADE)
    bin = models.ForeignKey("Bin", null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Required component for step"
        verbose_name_plural = "Required components for step"

    def __str__(self):
        return f"{self.quantity}× {self.component.name} for {self.step}"


class AssemblyStep(models.Model):
    assembly = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["assembly", "order"],
                name="unique_step_order_per_assembly",
            )
        ]

    def __str__(self):
        return f"{self.assembly.name} — Step {self.order}"

    @property
    def required_components(self):
        return self.steprequiredcomponent_set.all()

class StepObject(models.Model):
    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE)
    OBJECT_TYPE_TEXT = "text"
    OBJECT_TYPE_IMAGE = "image"

    object_type = models.CharField(
        max_length=20,
        choices=[
            (OBJECT_TYPE_TEXT, "Text"),
            (OBJECT_TYPE_IMAGE, "Image"),
        ]
    )
    position_x = models.FloatField()
    position_y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()
    z_index = models.IntegerField()
    text_content = models.TextField(blank=True)
    image_path = models.CharField(max_length=200, blank=True)
    font_size = models.IntegerField(default=40)

    def clean(self):
        super().clean()
        if self.object_type == self.OBJECT_TYPE_TEXT:
            if not (self.text_content or "").strip():
                raise ValidationError("Text objects must have non-empty text_content.")
        elif self.object_type == self.OBJECT_TYPE_IMAGE:
            if not (self.image_path or "").strip():
                raise ValidationError("Image objects must have a non-empty image_path.")

    def __str__(self):
        return f"{self.object_type} for {self.step}"
    
class AssemblyExecution(models.Model):
    assembly_type = models.ForeignKey(AssemblyType, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Execution of {self.assembly_type.name} by {self.operator.name}"
    
class StepExecution(models.Model):
    assembly_execution = models.ForeignKey(AssemblyExecution, on_delete=models.CASCADE)
    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Step {self.step.order} of {self.assembly_execution}"
    
class ErrorType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class EventType(models.TextChoices):
    BREAK_START = "BREAK_START", "Break started"
    BREAK_END = "BREAK_END", "Break ended"
    REPAIR_START = "REPAIR_START", "Repair started"
    REPAIR_END = "REPAIR_END", "Repair ended"
    WAIT_START = "WAIT_START", "Waiting for material started"
    WAIT_END = "WAIT_END", "Waiting for material ended"

class EventLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)

    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
    )

    operator = models.ForeignKey(
        Operator,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    assembly_execution = models.ForeignKey(
        AssemblyExecution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    step_execution = models.ForeignKey(
        StepExecution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    related_bin = models.ForeignKey(
        Bin,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.timestamp} — {self.event_type}"

class ErrorLog(models.Model):
    step_execution = models.ForeignKey(StepExecution, null=True, blank=True, on_delete=models.SET_NULL)
    error_type = models.ForeignKey(ErrorType, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Error {self.error_type.name} at {self.timestamp}"