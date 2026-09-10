# program.health.programs.beast3.py
# Beast System 3.0 — Deterministic Health Program Engine

from dataclasses import dataclass, field
import time
import hashlib

@dataclass
class ProgramDefinition:
    program_id: str
    name: str
    phases: list
    metadata: dict
    ts: float = field(default_factory=time.time)
    hash: str = ""

    def finalize(self):
        serialized = f"{self.program_id}{self.name}{self.phases}{self.metadata}{self.ts}".encode("utf-8")
        self.hash = hashlib.sha256(serialized).hexdigest()

@dataclass
class ProgramEvent:
    family_id: str
    program_id: str
    event_type: str
    phase: str
    metadata: dict
    ts: float = field(default_factory=time.time)
    hash: str = ""

    def finalize(self):
        serialized = f"{self.family_id}{self.program_id}{self.event_type}{self.phase}{self.metadata}{self.ts}".encode("utf-8")
        self.hash = hashlib.sha256(serialized).hexdigest()

@dataclass
class ProgramProfile:
    family_id: str
    enrollments: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    last_update: float = field(default_factory=time.time)

    def add_event(self, event: ProgramEvent):
        event.finalize()
        self.events.append(event)
        self.last_update = event.ts

class HealthProgramEngine:
    def __init__(self, kernel):
        self.kernel = kernel
        self.program_definitions = {}
        self.program_profiles = {}

    # -------------------------
    # Program Definition
    # -------------------------
    def define_program(self, program_id: str, name: str, phases: list, metadata: dict):
        definition = ProgramDefinition(program_id, name, phases, metadata)
        definition.finalize()
        self.program_definitions[program_id] = definition

        return self.kernel.dispatch(
            module="health.programs",
            action="define_program",
            payload={
                "program_id": program_id,
                "name": name,
                "phases": phases,
                "metadata": metadata
            }
        )

    # -------------------------
    # Enrollment
    # -------------------------
    def enroll(self, family_id: str, program_id: str):
        if program_id not in self.program_definitions:
            raise ValueError("Program not defined")

        if family_id not in self.program_profiles:
            self.program_profiles[family_id] = ProgramProfile(family_id)

        profile = self.program_profiles[family_id]
        profile.enrollments[program_id] = {
            "current_phase": self.program_definitions[program_id].phases[0],
            "completed": False,
            "ts": time.time()
        }

        event = ProgramEvent(
            family_id=family_id,
            program_id=program_id,
            event_type="enroll",
            phase=profile.enrollments[program_id]["current_phase"],
            metadata={}
        )
        profile.add_event(event)

        return self.kernel.dispatch(
            module="health.programs",
            action="enroll",
            payload={
                "family_id": family_id,
                "program_id": program_id,
                "phase": profile.enrollments[program_id]["current_phase"]
            }
        )

    # -------------------------
    # Phase Transition
    # -------------------------
    def advance_phase(self, family_id: str, program_id: str):
        if family_id not in self.program_profiles:
            raise ValueError("Profile not found")

        profile = self.program_profiles[family_id]
        if program_id not in profile.enrollments:
            raise ValueError("Not enrolled in program")

        definition = self.program_definitions[program_id]
        current_phase = profile.enrollments[program_id]["current_phase"]
        phases = definition.phases

        if current_phase not in phases:
            raise ValueError("Invalid phase")

        idx = phases.index(current_phase)
        if idx + 1 < len(phases):
            new_phase = phases[idx + 1]
            profile.enrollments[program_id]["current_phase"] = new_phase
        else:
            profile.enrollments[program_id]["completed"] = True
            new_phase = "completed"

        event = ProgramEvent(
            family_id=family_id,
            program_id=program_id,
            event_type="phase_transition",
            phase=new_phase,
            metadata={}
        )
        profile.add_event(event)

        return self.kernel.dispatch(
            module="health.programs",
            action="advance_phase",
            payload={
                "family_id": family_id,
                "program_id": program_id,
                "new_phase": new_phase
            }
        )

    # -------------------------
    # Retrieval
    # -------------------------
    def get_profile(self, family_id: str):
        return self.program_profiles.get(family_id, None)

    def get_program(self, program_id: str):
        return self.program_definitions.get(program_id, None)
