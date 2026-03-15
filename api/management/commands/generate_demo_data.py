import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Operator,
    OperatorRole,
    OperatorRoleAssignment,
    AssemblyType,
    AssemblyStep,
    AssemblyExecution,
    StepExecution,
    EventLog,
    EventType,
)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class Command(BaseCommand):
    help = "Generate realistic demo data: operators, assembly types, steps, executions, step executions, and downtime events."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=60, help="How many days back to generate data.")
        parser.add_argument("--operators", type=int, default=10, help="How many operators to ensure exist.")
        parser.add_argument("--assembly-types", type=int, default=10, help="How many assembly types to ensure exist.")
        parser.add_argument("--steps-per-type", type=int, default=5, help="How many steps per assembly type.")

        parser.add_argument("--executions", type=int, default=2500, help="How many AssemblyExecution rows to generate.")
        parser.add_argument("--fail-rate", type=float, default=0.05, help="Probability that execution is not completed.")
        parser.add_argument("--event-rate", type=float, default=0.25, help="Probability to add downtime events to an execution.")
        parser.add_argument("--outlier-rate", type=float, default=0.02, help="Probability to create very long execution time.")
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        now = timezone.now()
        window_start = now - timedelta(days=opts["days"])

        operators = self.ensure_operators(opts["operators"])
        assembly_types = self.ensure_assembly_types(opts["assembly_types"])
        self.ensure_steps_for_types(assembly_types, opts["steps_per_type"])

        # Operator “speed profile”: lower = faster
        op_speed = {op.id: clamp(random.gauss(1.0, 0.18), 0.70, 1.45) for op in operators}
        # Assembly complexity: higher = slower
        type_complexity = {at.id: clamp(random.gauss(1.0, 0.28), 0.70, 2.00) for at in assembly_types}

        # Simple availability model: avoid overlaps per operator, plus random downtime gaps
        operator_next_free = {op.id: window_start for op in operators}

        created_exec = 0
        created_steps = 0
        created_events = 0

        days = opts["days"]

        # Shift settings
        shift_start_hour = 6          # 06:00
        shift_seconds = 8 * 3600      # 8-hour shift

        for day_index in range(days):
            day_start = window_start + timedelta(days=day_index)

            # reset operator availability at start of each day/shift
            operator_next_free = {
                op.id: day_start + timedelta(hours=shift_start_hour)
                for op in operators
            }

            # choose how many assemblies this day (50–200)
            daily_target = random.randint(50, 200)

            for _ in range(daily_target):
                op = random.choice(operators)
                at = random.choice(assembly_types)

                # Determine number of steps for this assembly type
                steps = list(AssemblyStep.objects.filter(assembly=at).order_by("order"))
                n_steps = max(1, len(steps))

                # random time within shift window
                random_offset = random.randint(0, shift_seconds - 1)
                base_start = day_start + timedelta(
                    hours=shift_start_hour,
                    seconds=random_offset,
                )

                # avoid overlapping for this operator
                start_time = max(base_start, operator_next_free[op.id])


            # Decide completion
            is_completed = (random.random() >= opts["fail_rate"])

            # Base duration: depends on steps + operator + complexity
            # Each assembly should take between 250 and 350 seconds
            duration = random.randint(250, 350)

            # Create execution with auto timestamps, then overwrite timestamps via update()
            exec_obj = AssemblyExecution.objects.create(
                assembly_type=at,
                operator=op,
                is_completed=is_completed,
                end_time=None,
            )

            if is_completed:
                end_time = start_time + timedelta(seconds=duration)
            else:
                # Not completed: sometimes no end_time, sometimes partial
                end_time = None if random.random() < 0.7 else start_time + timedelta(
                    seconds=int(duration * random.uniform(0.2, 0.7))
                )

            AssemblyExecution.objects.filter(id=exec_obj.id).update(
                start_time=start_time,
                end_time=end_time,
                is_completed=is_completed,
            )

            created_exec += 1

            # Step executions (only for the time we actually have)
            # If end_time is None, generate partial steps up to "work_time"
            work_end = end_time if end_time else (start_time + timedelta(seconds=int(duration * random.uniform(0.2, 0.8))))
            work_seconds = max(1, int((work_end - start_time).total_seconds()))

            # Distribute time across steps using random weights
            weights = [random.uniform(0.7, 1.3) for _ in range(n_steps)]
            wsum = sum(weights)

            step_cursor = start_time
            for step, w in zip(steps, weights):
                step_sec = int((w / wsum) * work_seconds)
                step_sec = max(1, step_sec)
                step_end = step_cursor + timedelta(seconds=step_sec)

                if step_end > work_end:
                    break

                step_exec = StepExecution.objects.create(
                    assembly_execution=exec_obj,
                    step=step,
                    is_completed=True,
                    end_time=None,
                )

                StepExecution.objects.filter(id=step_exec.id).update(
                    start_time=step_cursor,
                    end_time=step_end,
                    is_completed=True,
                )

                created_steps += 1
                step_cursor = step_end

            # Add downtime events sometimes (BREAK / WAIT / REPAIR)
            if random.random() < opts["event_rate"]:
                created_events += self.add_random_events(exec_obj, op, start_time, work_end)

            # Operator next free time (add small gap)
            operator_next_free[op.id] = work_end + timedelta(seconds=random.randint(20, 180))

        self.stdout.write(self.style.SUCCESS(
            f"Done.\n"
            f"Executions: {created_exec}\n"
            f"Step executions: {created_steps}\n"
            f"Event logs: {created_events}"
        ))

    # ---------------- helpers ----------------

    def ensure_operators(self, n_ops):
        ops = list(Operator.objects.all().order_by("id"))
        if len(ops) >= n_ops:
            return ops[:n_ops]

        # Create missing operators with unique employee_id
        next_idx = len(ops) + 1
        for i in range(next_idx, n_ops + 1):
            Operator.objects.create(
                name=f"Operator {i}",
                employee_id=f"EMP-{i:04d}",
            )
        return list(Operator.objects.all().order_by("id"))[:n_ops]

    def ensure_assembly_types(self, n_types):
        types = list(AssemblyType.objects.all().order_by("id"))
        if len(types) >= n_types:
            return types[:n_types]

        next_idx = len(types) + 1
        for i in range(next_idx, n_types + 1):
            AssemblyType.objects.create(
                name=f"Assembly Type {i}",
                description="Generated demo assembly type",
                version="1.0",
                is_active=True,
            )
        return list(AssemblyType.objects.all().order_by("id"))[:n_types]

    def ensure_steps_for_types(self, assembly_types, steps_per_type):
        for at in assembly_types:
            existing = AssemblyStep.objects.filter(assembly=at).count()
            if existing >= steps_per_type:
                continue
            for order in range(existing + 1, steps_per_type + 1):
                AssemblyStep.objects.create(
                    assembly=at,
                    order=order,
                    title=f"Step {order}",
                    description="Generated demo step",
                )

    def add_random_events(self, exec_obj, op, start_time, work_end):
        """
        Inserts at most 1 downtime-like event pair into EventLog linked to the execution.
        """
        total_seconds = max(60, int((work_end - start_time).total_seconds()))

        # ~50% chance any downtime exists at all
        if random.random() > 0.5:
            return 0

        pair_type = random.choice(["BREAK", "WAIT", "REPAIR"])

        if pair_type == "BREAK":
            ev_start, ev_end = EventType.BREAK_START, EventType.BREAK_END
            dur = random.randint(60, 10 * 60)
        elif pair_type == "WAIT":
            ev_start, ev_end = EventType.WAIT_START, EventType.WAIT_END
            dur = random.randint(60, 20 * 60)
        else:
            ev_start, ev_end = EventType.REPAIR_START, EventType.REPAIR_END
            dur = random.randint(2 * 60, 30 * 60)

        max_start = max(1, total_seconds - dur - 1)
        offset = random.randint(0, max_start)
        t0 = start_time + timedelta(seconds=offset)
        t1 = t0 + timedelta(seconds=dur)
        if t1 > work_end:
            t1 = work_end

        log1 = EventLog.objects.create(
            event_type=ev_start,
            operator=op,
            assembly_execution=exec_obj,
            notes=f"Generated {pair_type.lower()} start",
        )
        EventLog.objects.filter(id=log1.id).update(timestamp=t0)

        log2 = EventLog.objects.create(
            event_type=ev_end,
            operator=op,
            assembly_execution=exec_obj,
            notes=f"Generated {pair_type.lower()} end",
        )
        EventLog.objects.filter(id=log2.id).update(timestamp=t1)

        return 2
