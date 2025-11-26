import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import joinedload, relationship, sessionmaker

Base = declarative_base()


class Printer(Base):
    __tablename__ = 'printers'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    last_service = Column(String)
    moonraker_host = Column(String)
    moonraker_port = Column(Integer, default=7125)
    moonraker_printer = Column(String)  # Optional identifier for multi-printer hosts
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime)
    is_virtual = Column(Boolean, default=False)
    virtual_status = Column(String, default="idle")

    tasks = relationship('Task', back_populates='printer')


class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    nozzle_tmp = Column(String)
    table_tmp = Column(String)


class Coil(Base):
    __tablename__ = 'coils'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    material_id = Column(Integer, ForeignKey('materials.id'))
    remains = Column(Float)

    material = relationship('Material')
    tasks = relationship('Task', back_populates='coil')


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    desc = Column(Text)
    color = Column(String, default="#888888")

    tasks = relationship('Task', back_populates='project')


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    status = Column(String, default='pending')
    notes = Column(Text)
    printer_id = Column(Integer, ForeignKey('printers.id'))
    coil_id = Column(Integer, ForeignKey('coils.id'))
    material_amount = Column(Float)
    project_id = Column(Integer, ForeignKey('projects.id'))
    time_start = Column(String)
    time_end = Column(String)
    progress = Column(Integer)
    model_gcode = Column(Text)  # Stores path to uploaded G-code file
    gcode_original_name = Column(String)
    estimated_filament = Column(Float)
    estimated_time_minutes = Column(Float)
    gcode_uploaded_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    printer = relationship('Printer', back_populates='tasks')
    coil = relationship('Coil', back_populates='tasks')
    project = relationship('Project', back_populates='tasks')


class DBModel:
    def __init__(self, db_path: str = 'database.db'):
        self.db_path = db_path
        db_exists = os.path.exists(self.db_path)
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        if not db_exists:
            Base.metadata.create_all(self.engine)
        else:
            Base.metadata.create_all(self.engine)
            self._ensure_schema()
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def _ensure_schema(self):
        """Ensure the current SQLite schema has all new columns."""
        with self.engine.connect() as conn:
            self._add_column_if_missing(conn, 'printers', 'moonraker_host', "TEXT")
            self._add_column_if_missing(conn, 'printers', 'moonraker_port', "INTEGER DEFAULT 7125")
            self._add_column_if_missing(conn, 'printers', 'moonraker_printer', "TEXT")
            self._add_column_if_missing(conn, 'printers', 'is_active', "BOOLEAN DEFAULT 1")
            self._add_column_if_missing(conn, 'printers', 'last_seen', "DATETIME")
            self._add_column_if_missing(conn, 'printers', 'is_virtual', "BOOLEAN DEFAULT 0")
            self._add_column_if_missing(conn, 'printers', 'virtual_status', "TEXT DEFAULT 'idle'")

            self._add_column_if_missing(conn, 'projects', 'color', "TEXT DEFAULT '#888888'")

            self._add_column_if_missing(conn, 'tasks', 'name', "TEXT")
            self._add_column_if_missing(conn, 'tasks', 'status', "TEXT DEFAULT 'pending'")
            self._add_column_if_missing(conn, 'tasks', 'notes', "TEXT")
            self._add_column_if_missing(conn, 'tasks', 'gcode_original_name', "TEXT")
            self._add_column_if_missing(conn, 'tasks', 'estimated_filament', "FLOAT")
            self._add_column_if_missing(conn, 'tasks', 'estimated_time_minutes', "FLOAT")
            self._add_column_if_missing(conn, 'tasks', 'gcode_uploaded_at', "DATETIME")
            self._add_column_if_missing(conn, 'tasks', 'created_at', "DATETIME")
            self._add_column_if_missing(conn, 'tasks', 'updated_at', "DATETIME")
            conn.commit()

    @staticmethod
    def _add_column_if_missing(conn, table_name: str, column_name: str, column_def: str):
        existing = conn.execute(text(f"PRAGMA table_info({table_name})"))
        columns = {row[1] for row in existing}
        if column_name not in columns:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))

    # Printer helpers
    def add_printer(self, name: str, last_service: Optional[str] = None, **kwargs) -> Printer:
        session = self.get_session()
        try:
            printer = Printer(name=name, last_service=last_service, **kwargs)
            session.add(printer)
            session.commit()
            session.refresh(printer)
            return printer
        finally:
            session.close()

    def add_virtual_printer(self, name: str, status: str = "idle") -> Printer:
        session = self.get_session()
        try:
            printer = Printer(
                name=name,
                is_virtual=True,
                virtual_status=status or "idle",
                is_active=True,
                last_seen=datetime.now(timezone.utc),
            )
            session.add(printer)
            session.commit()
            session.refresh(printer)
            return printer
        finally:
            session.close()

    def upsert_printer(
        self,
        name: Optional[str],
        moonraker_host: str,
        moonraker_port: int = 7125,
        moonraker_printer: Optional[str] = None,
        last_service: Optional[str] = None,
        is_active: bool = True,
        **kwargs,
    ) -> Printer:
        session = self.get_session()
        try:
            printer = (
                session.query(Printer)
                .filter_by(
                    moonraker_host=moonraker_host,
                    moonraker_port=moonraker_port,
                    moonraker_printer=moonraker_printer,
                )
                .first()
            )
            if printer:
                if name:
                    printer.name = name
                if last_service:
                    printer.last_service = last_service
                printer.is_active = is_active
                if 'is_virtual' in kwargs:
                    printer.is_virtual = kwargs.get('is_virtual', False)
                if 'virtual_status' in kwargs and kwargs.get('virtual_status'):
                    printer.virtual_status = kwargs.get('virtual_status')
            else:
                printer = Printer(
                    name=name or f"Printer@{moonraker_host}",
                    moonraker_host=moonraker_host,
                    moonraker_port=moonraker_port,
                    moonraker_printer=moonraker_printer,
                    last_service=last_service,
                    is_active=is_active,
                    is_virtual=kwargs.get('is_virtual', False),
                    virtual_status=kwargs.get('virtual_status') or "idle",
                )
                session.add(printer)

            if is_active:
                printer.last_seen = datetime.now(timezone.utc)

            session.commit()
            session.refresh(printer)
            return printer
        finally:
            session.close()

    def set_printer_active(self, printer_id: int, is_active: bool):
        session = self.get_session()
        try:
            printer = session.query(Printer).get(printer_id)
            if not printer:
                return
            printer.is_active = is_active
            if is_active:
                printer.last_seen = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def get_printer_by_id(self, printer_id: int) -> Optional[Printer]:
        session = self.get_session()
        try:
            return session.query(Printer).get(printer_id)
        finally:
            session.close()

    def get_printers(self, include_inactive: bool = True):
        session = self.get_session()
        try:
            query = session.query(Printer)
            if not include_inactive:
                query = query.filter(Printer.is_active.is_(True))
            return query.all()
        finally:
            session.close()

    def delete_printer(self, printer_id: int) -> bool:
        session = self.get_session()
        try:
            printer = session.query(Printer).get(printer_id)
            if not printer:
                return False
            session.delete(printer)
            session.commit()
            return True
        finally:
            session.close()

    # Material / coil / project helpers
    def add_material(self, name, nozzle_tmp, table_tmp):
        session = self.get_session()
        try:
            material = Material(name=name, nozzle_tmp=nozzle_tmp, table_tmp=table_tmp)
            session.add(material)
            session.commit()
            session.refresh(material)
            return material
        finally:
            session.close()

    def get_materials(self):
        session = self.get_session()
        try:
            return session.query(Material).all()
        finally:
            session.close()

    def add_coil(self, name, material_id, remains):
        session = self.get_session()
        try:
            coil = Coil(name=name, material_id=material_id, remains=remains)
            session.add(coil)
            session.commit()
            session.refresh(coil)
            return coil
        finally:
            session.close()

    def get_coils(self):
        session = self.get_session()
        try:
            return (
                session.query(Coil)
                .all()
            )
        finally:
            session.close()

    def add_project(self, name, desc, color="#888888"):
        session = self.get_session()
        try:
            project = Project(name=name, desc=desc, color=color)
            session.add(project)
            session.commit()
            session.refresh(project)
            return project
        finally:
            session.close()

    def update_project(self, project_id: int, **kwargs) -> Optional[Project]:
        session = self.get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project:
                return None
            data = self._filter_model_kwargs(Project, kwargs)
            for key, value in data.items():
                setattr(project, key, value)
            session.commit()
            session.refresh(project)
            return project
        finally:
            session.close()

    def delete_project(self, project_id: int) -> bool:
        session = self.get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project:
                return False
            try:
                session.delete(project)
                session.commit()
                return True
            except SQLAlchemyError:
                session.rollback()
                return False
        finally:
            session.close()

    def get_projects(self):
        session = self.get_session()
        try:
            return session.query(Project).all()
        finally:
            session.close()

    def get_project(self, project_id: int) -> Optional[Project]:
        session = self.get_session()
        try:
            return session.query(Project).get(project_id)
        finally:
            session.close()

    # Task helpers
    def add_task(self, **kwargs) -> Task:
        session = self.get_session()
        try:
            data = self._filter_model_kwargs(Task, kwargs)
            if 'created_at' not in data:
                data['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in data:
                data['updated_at'] = datetime.now(timezone.utc)
            task = Task(**data)
            session.add(task)
            session.commit()
            session.refresh(task)
            return task
        finally:
            session.close()

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        session = self.get_session()
        try:
            task = session.query(Task).get(task_id)
            if not task:
                return None
            data = self._filter_model_kwargs(Task, kwargs)
            for key, value in data.items():
                setattr(task, key, value)
            task.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(task)
            return task
        finally:
            session.close()

    def delete_task(self, task_id: int) -> bool:
        session = self.get_session()
        try:
            task = session.query(Task).get(task_id)
            if not task:
                return False
            session.delete(task)
            session.commit()
            return True
        finally:
            session.close()

    def get_tasks(self):
        session = self.get_session()
        try:
            return (
                session.query(Task)
                .options(
                    joinedload(Task.project),
                    joinedload(Task.printer),
                    joinedload(Task.coil).joinedload(Coil.material),
                )
                .all()
            )
        finally:
            session.close()

    def get_task(self, task_id: int) -> Optional[Task]:
        session = self.get_session()
        try:
            return (
                session.query(Task)
                .options(
                    joinedload(Task.project),
                    joinedload(Task.printer),
                    joinedload(Task.coil).joinedload(Coil.material),
                )
                .get(task_id)
            )
        finally:
            session.close()

    @staticmethod
    def _filter_model_kwargs(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
        valid_keys = {column.name for column in model_cls.__table__.columns}
        return {key: value for key, value in data.items() if key in valid_keys}
