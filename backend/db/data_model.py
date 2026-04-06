import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    event,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, joinedload, relationship, sessionmaker

logger = logging.getLogger(__name__)

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
    print_hours = Column(Float, default=0.0)  # Общее время печати в часах
    nozzle_diameter = Column(Float, default=0.4)  # Диаметр сопла в мм
    active_coil_id = Column(Integer, ForeignKey('coils.id'))  # Активная катушка принтера
    removal_confirmed = Column(Boolean, default=False)  # Подтверждение уборки детали после печати
    # Поля для оффлайн-принтеров (ручной ввод данных)
    manual_progress = Column(Integer, default=0)  # Прогресс печати 0-100%
    manual_filename = Column(String)  # Имя файла/модели
    manual_print_start = Column(DateTime)  # Время начала печати

    tasks = relationship('Task', back_populates='printer')
    maintenance_records = relationship('MaintenanceRecord', back_populates='printer', cascade='all, delete-orphan')
    active_coil = relationship('Coil', foreign_keys=[active_coil_id])


class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    nozzle_tmp = Column(String)
    table_tmp = Column(String)


class Vendor(Base):
    """Производитель филамента."""
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    comment = Column(Text)
    empty_spool_weight = Column(Float)  # Дефолтный вес пустой катушки в граммах

    filaments = relationship('Filament', back_populates='vendor')


class Filament(Base):
    """Филамент - продукт производителя с типом пластика."""
    __tablename__ = 'filaments'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    name = Column(String, nullable=False)  # Название продукта (например "PLA+ Premium")
    material = Column(String)  # Тип пластика (PLA, PETG, ABS, TPU и т.д.)
    color_hex = Column(String(7))  # Цвет (#RRGGBB)
    diameter = Column(Float, default=1.75)  # Диаметр в мм
    density = Column(Float)  # Плотность г/см³
    weight = Column(Float, default=1000)  # Стандартный вес филамента в граммах
    empty_spool_weight = Column(Float, default=200)  # Стандартный вес пустой катушки в граммах
    description = Column(Text)  # Описание

    vendor = relationship('Vendor', back_populates='filaments')
    coils = relationship('Coil', back_populates='filament')


class Coil(Base):
    """Катушка филамента."""
    __tablename__ = 'coils'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    filament_id = Column(Integer, ForeignKey('filaments.id'))  # Основная связь с филаментом
    material_id = Column(Integer, ForeignKey('materials.id'))  # Deprecated, для совместимости
    vendor_id = Column(Integer, ForeignKey('vendors.id'))  # Deprecated, для совместимости
    remains = Column(Float)  # Остаток филамента в граммах

    # Расширенные поля (Spoolman-like)
    spool_weight = Column(Float)  # Вес пустой катушки в граммах
    initial_weight = Column(Float)  # Начальный вес филамента в граммах
    color_hex = Column(String(7))  # Цвет филамента (#RRGGBB), может отличаться от филамента
    price = Column(Float)  # Цена катушки
    location = Column(String)  # Местоположение хранения
    lot_nr = Column(String)  # Номер партии
    comment = Column(Text)  # Примечания
    archived = Column(Boolean, default=False)  # Архивирована ли
    first_used = Column(DateTime)  # Дата первого использования
    last_used = Column(DateTime)  # Дата последнего использования

    filament = relationship('Filament', back_populates='coils')
    material = relationship('Material')  # Deprecated
    vendor = relationship('Vendor')  # Deprecated
    tasks = relationship('Task', back_populates='coil')
    history = relationship('SpoolHistory', back_populates='coil', cascade='all, delete-orphan')

    @property
    def used_weight(self):
        """Вычисляемое поле: использовано = начальный - остаток."""
        if self.initial_weight is None or self.remains is None:
            return None
        return self.initial_weight - self.remains

    @property
    def total_weight(self):
        """Полный вес катушки с филаментом."""
        spool = self.spool_weight or 0
        filament = self.remains or 0
        return spool + filament

    @property
    def remains_percent(self):
        """Процент оставшегося филамента."""
        if self.initial_weight is None or self.initial_weight <= 0:
            return None
        if self.remains is None:
            return None
        return round((self.remains / self.initial_weight) * 100, 1)

    @property
    def remains_status(self):
        """Статус остатка: ok (>50%), warning (>20%), critical (<=20%)."""
        pct = self.remains_percent
        if pct is None:
            return 'unknown'
        if pct > 50:
            return 'ok'
        elif pct > 20:
            return 'warning'
        return 'critical'


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
    # Метаданные G-code
    gcode_layer_count = Column(Integer)
    gcode_layer_height = Column(Float)
    gcode_nozzle_temp = Column(Integer)
    gcode_bed_temp = Column(Integer)
    gcode_slicer = Column(String)
    # Поля для отслеживания печати
    moonraker_filename = Column(String)  # Имя файла на принтере (для связи с активной печатью)
    actual_filament_used = Column(Float)  # Фактический расход филамента (мм)
    actual_print_time = Column(Float)     # Фактическое время печати (минуты)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    printer = relationship('Printer', back_populates='tasks')
    coil = relationship('Coil', back_populates='tasks')
    project = relationship('Project', back_populates='tasks')


class SpoolHistory(Base):
    """История расхода филамента с катушки."""
    __tablename__ = 'spool_history'
    id = Column(Integer, primary_key=True)
    coil_id = Column(Integer, ForeignKey('coils.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'))  # Может быть NULL при ручной корректировке
    used_weight = Column(Float, nullable=False)  # Использовано в граммах (отрицательное = возврат)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text)  # Примечание (ручное списание, отмена и т.д.)

    coil = relationship('Coil', back_populates='history')
    task = relationship('Task')


class MaintenanceType(Base):
    """Типы технического обслуживания."""
    __tablename__ = 'maintenance_types'
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)  # 'nozzle', 'rollers', 'extruder'
    name = Column(String, nullable=False)  # Человекочитаемое название
    interval_hours = Column(Float, nullable=False)  # Интервал в часах печати
    description = Column(Text)  # Описание обслуживания

    records = relationship('MaintenanceRecord', back_populates='maintenance_type')


class MaintenanceRecord(Base):
    """Записи о выполненном техническом обслуживании."""
    __tablename__ = 'maintenance_records'
    id = Column(Integer, primary_key=True)
    printer_id = Column(Integer, ForeignKey('printers.id'), nullable=False)
    maintenance_type_id = Column(Integer, ForeignKey('maintenance_types.id'), nullable=False)
    performed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # Когда выполнено
    print_hours_at = Column(Float, default=0.0)  # Часы печати в момент обслуживания
    notes = Column(Text)  # Комментарий пользователя
    is_forced = Column(Boolean, default=False)  # Принудительное обслуживание

    printer = relationship('Printer', back_populates='maintenance_records')
    maintenance_type = relationship('MaintenanceType', back_populates='records')


# Предустановленные типы обслуживания
DEFAULT_MAINTENANCE_TYPES = [
    {'code': 'nozzle', 'name': 'Замена сопел', 'interval_hours': 200.0, 'description': 'Замена сопла экструдера'},
    {'code': 'rollers', 'name': 'Замена роликов', 'interval_hours': 500.0, 'description': 'Замена роликов подачи филамента'},
    {'code': 'extruder', 'name': 'Обслуживание экструдера', 'interval_hours': 300.0, 'description': 'Чистка и смазка экструдера'},
]


class DBModel:
    def __init__(self, db_path: str = 'database.db'):
        self.db_path = db_path
        db_exists = os.path.exists(self.db_path)
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            pool_size=10,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=3600,
            connect_args={
                "check_same_thread": False,
                "timeout": 15,
            },
        )

        # PRAGMA-оптимизации для каждого нового соединения
        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-8000")  # 8 MB
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=67108864")  # 64 MB
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        if not db_exists:
            logger.info("Создание новой БД: %s", self.db_path)
            Base.metadata.create_all(self.engine)
        else:
            logger.info("Подключение к существующей БД: %s", self.db_path)
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
            self._add_column_if_missing(conn, 'printers', 'print_hours', "FLOAT DEFAULT 0.0")
            self._add_column_if_missing(conn, 'printers', 'nozzle_diameter', "FLOAT DEFAULT 0.4")
            self._add_column_if_missing(conn, 'printers', 'removal_confirmed', "BOOLEAN DEFAULT 0")
            # Поля для оффлайн-принтеров
            self._add_column_if_missing(conn, 'printers', 'manual_progress', "INTEGER DEFAULT 0")
            self._add_column_if_missing(conn, 'printers', 'manual_filename', "TEXT")
            self._add_column_if_missing(conn, 'printers', 'manual_print_start', "DATETIME")

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
            # Метаданные G-code
            self._add_column_if_missing(conn, 'tasks', 'gcode_layer_count', "INTEGER")
            self._add_column_if_missing(conn, 'tasks', 'gcode_layer_height', "FLOAT")
            self._add_column_if_missing(conn, 'tasks', 'gcode_nozzle_temp', "INTEGER")
            self._add_column_if_missing(conn, 'tasks', 'gcode_bed_temp', "INTEGER")
            self._add_column_if_missing(conn, 'tasks', 'gcode_slicer', "TEXT")
            # Поля для отслеживания печати
            self._add_column_if_missing(conn, 'tasks', 'moonraker_filename', "TEXT")
            self._add_column_if_missing(conn, 'tasks', 'actual_filament_used', "FLOAT")
            self._add_column_if_missing(conn, 'tasks', 'actual_print_time', "FLOAT")

            # Активная катушка принтера
            self._add_column_if_missing(conn, 'printers', 'active_coil_id', "INTEGER REFERENCES coils(id)")

            # Расширенные поля катушек (Spoolman-like)
            self._add_column_if_missing(conn, 'coils', 'vendor_id', "INTEGER REFERENCES vendors(id)")
            self._add_column_if_missing(conn, 'coils', 'spool_weight', "FLOAT")
            self._add_column_if_missing(conn, 'coils', 'initial_weight', "FLOAT")
            self._add_column_if_missing(conn, 'coils', 'color_hex', "TEXT")
            self._add_column_if_missing(conn, 'coils', 'price', "FLOAT")
            self._add_column_if_missing(conn, 'coils', 'location', "TEXT")
            self._add_column_if_missing(conn, 'coils', 'lot_nr', "TEXT")
            self._add_column_if_missing(conn, 'coils', 'comment', "TEXT")
            self._add_column_if_missing(conn, 'coils', 'archived', "BOOLEAN DEFAULT 0")
            self._add_column_if_missing(conn, 'coils', 'first_used', "DATETIME")
            self._add_column_if_missing(conn, 'coils', 'last_used', "DATETIME")

            # Таблица filaments (если не существует)
            self._create_table_if_missing(conn, 'filaments', """
                id INTEGER PRIMARY KEY,
                vendor_id INTEGER REFERENCES vendors(id),
                name TEXT NOT NULL,
                material TEXT,
                color_hex TEXT,
                diameter FLOAT DEFAULT 1.75,
                density FLOAT,
                weight FLOAT DEFAULT 1000,
                empty_spool_weight FLOAT DEFAULT 200,
                description TEXT
            """)
            # Миграция: добавить поле empty_spool_weight в существующую таблицу filaments
            self._add_column_if_missing(conn, 'filaments', 'empty_spool_weight', "FLOAT DEFAULT 200")

            # Связь катушки с филаментом
            self._add_column_if_missing(conn, 'coils', 'filament_id', "INTEGER REFERENCES filaments(id)")

            conn.commit()

    @staticmethod
    def _add_column_if_missing(conn, table_name: str, column_name: str, column_def: str):
        existing = conn.execute(text(f"PRAGMA table_info({table_name})"))
        columns = {row[1] for row in existing}
        if column_name not in columns:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))

    @staticmethod
    def _create_table_if_missing(conn, table_name: str, columns_def: str):
        """Создать таблицу если она не существует."""
        existing = conn.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        ))
        if not existing.fetchone():
            conn.execute(text(f"CREATE TABLE {table_name} ({columns_def})"))

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
            printer = session.get(Printer, printer_id)
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
            return session.get(Printer, printer_id)
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
            printer = session.get(Printer, printer_id)
            if not printer:
                return False
            session.delete(printer)
            session.commit()
            return True
        finally:
            session.close()

    def update_printer(self, printer_id: int, **kwargs) -> Optional[Printer]:
        """Обновление принтера по ID."""
        session = self.get_session()
        try:
            printer = session.get(Printer, printer_id)
            if not printer:
                return None
            data = self._filter_model_kwargs(Printer, kwargs)
            for key, value in data.items():
                setattr(printer, key, value)
            session.commit()
            session.refresh(printer)
            return printer
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

    # === Vendor helpers ===

    def add_vendor(self, name: str, comment: Optional[str] = None,
                   empty_spool_weight: Optional[float] = None) -> Vendor:
        """Добавить производителя."""
        session = self.get_session()
        try:
            vendor = Vendor(name=name, comment=comment, empty_spool_weight=empty_spool_weight)
            session.add(vendor)
            session.commit()
            session.refresh(vendor)
            return vendor
        finally:
            session.close()

    def get_vendors(self):
        """Получить всех производителей."""
        session = self.get_session()
        try:
            return session.query(Vendor).all()
        finally:
            session.close()

    def get_vendor(self, vendor_id: int) -> Optional[Vendor]:
        """Получить производителя по ID."""
        session = self.get_session()
        try:
            return session.get(Vendor, vendor_id)
        finally:
            session.close()

    def update_vendor(self, vendor_id: int, **kwargs) -> Optional[Vendor]:
        """Обновить производителя."""
        session = self.get_session()
        try:
            vendor = session.get(Vendor, vendor_id)
            if not vendor:
                return None
            data = self._filter_model_kwargs(Vendor, kwargs)
            for key, value in data.items():
                setattr(vendor, key, value)
            session.commit()
            session.refresh(vendor)
            return vendor
        finally:
            session.close()

    def delete_vendor(self, vendor_id: int) -> bool:
        """Удалить производителя."""
        session = self.get_session()
        try:
            vendor = session.get(Vendor, vendor_id)
            if not vendor:
                return False
            session.delete(vendor)
            session.commit()
            return True
        except SQLAlchemyError:
            logger.exception("Ошибка удаления производителя id=%s", vendor_id)
            session.rollback()
            return False
        finally:
            session.close()

    # === Filament helpers ===

    def add_filament(self, name: str, vendor_id: Optional[int] = None,
                     material: Optional[str] = None, **kwargs) -> Filament:
        """Добавить филамент."""
        session = self.get_session()
        try:
            data = self._filter_model_kwargs(Filament, kwargs)
            filament = Filament(name=name, vendor_id=vendor_id, material=material, **data)
            session.add(filament)
            session.commit()
            filament_id = filament.id
        finally:
            session.close()
        # Возвращаем с eager-загруженным vendor
        return self.get_filament(filament_id)

    def get_filaments(self, vendor_id: Optional[int] = None, material: Optional[str] = None):
        """Получить филаменты с фильтрами."""
        session = self.get_session()
        try:
            query = session.query(Filament).options(joinedload(Filament.vendor))
            if vendor_id is not None:
                query = query.filter(Filament.vendor_id == vendor_id)
            if material:
                query = query.filter(Filament.material == material)
            return query.all()
        finally:
            session.close()

    def get_filament(self, filament_id: int) -> Optional[Filament]:
        """Получить филамент по ID."""
        session = self.get_session()
        try:
            return session.get(
                Filament, filament_id,
                options=[joinedload(Filament.vendor)],
            )
        finally:
            session.close()

    def update_filament(self, filament_id: int, **kwargs) -> Optional[Filament]:
        """Обновить филамент."""
        session = self.get_session()
        try:
            filament = session.get(Filament, filament_id)
            if not filament:
                return None
            data = self._filter_model_kwargs(Filament, kwargs)
            for key, value in data.items():
                setattr(filament, key, value)
            session.commit()
        finally:
            session.close()
        # Возвращаем с eager-загруженным vendor
        return self.get_filament(filament_id)

    def delete_filament(self, filament_id: int) -> bool:
        """Удалить филамент."""
        session = self.get_session()
        try:
            filament = session.get(Filament, filament_id)
            if not filament:
                return False
            session.delete(filament)
            session.commit()
            return True
        except SQLAlchemyError:
            logger.exception("Ошибка удаления филамента id=%s", filament_id)
            session.rollback()
            return False
        finally:
            session.close()

    # === Coil helpers (расширенные) ===

    def add_coil(self, name: str, remains: float, filament_id: Optional[int] = None,
                 material_id: Optional[int] = None, **kwargs) -> Coil:
        """Добавить катушку с расширенными полями."""
        session = self.get_session()
        try:
            data = self._filter_model_kwargs(Coil, kwargs)
            coil = Coil(name=name, remains=remains, filament_id=filament_id,
                       material_id=material_id, **data)
            session.add(coil)
            session.commit()
            session.refresh(coil)
            return coil
        finally:
            session.close()

    def get_coils(self, filament_id: Optional[int] = None, material_id: Optional[int] = None,
                  vendor_id: Optional[int] = None, archived: Optional[bool] = None,
                  include_archived: bool = False):
        """Получить катушки с фильтрами."""
        session = self.get_session()
        try:
            query = session.query(Coil).options(
                joinedload(Coil.filament).joinedload(Filament.vendor),
                joinedload(Coil.material),
                joinedload(Coil.vendor),
            )
            if filament_id is not None:
                query = query.filter(Coil.filament_id == filament_id)
            if material_id is not None:
                query = query.filter(Coil.material_id == material_id)
            if vendor_id is not None:
                query = query.filter(Coil.vendor_id == vendor_id)
            if archived is not None:
                query = query.filter(Coil.archived == archived)
            elif not include_archived:
                query = query.filter((Coil.archived.is_(False)) | (Coil.archived.is_(None)))
            return query.all()
        finally:
            session.close()

    def get_coil(self, coil_id: int) -> Optional[Coil]:
        """Получить катушку по ID с загрузкой связей."""
        session = self.get_session()
        try:
            return session.get(
                Coil, coil_id,
                options=[
                    joinedload(Coil.filament).joinedload(Filament.vendor),
                    joinedload(Coil.material),
                    joinedload(Coil.vendor),
                    joinedload(Coil.history),
                ],
            )
        finally:
            session.close()

    def update_coil(self, coil_id: int, **kwargs) -> Optional[Coil]:
        """Обновить катушку."""
        session = self.get_session()
        try:
            coil = session.get(Coil, coil_id)
            if not coil:
                return None
            data = self._filter_model_kwargs(Coil, kwargs)
            for key, value in data.items():
                setattr(coil, key, value)
            session.commit()
            session.refresh(coil)
            return coil
        finally:
            session.close()

    def delete_coil(self, coil_id: int) -> bool:
        """Удалить катушку."""
        session = self.get_session()
        try:
            coil = session.get(Coil, coil_id)
            if not coil:
                return False
            session.delete(coil)
            session.commit()
            return True
        except SQLAlchemyError:
            logger.exception("Ошибка удаления катушки id=%s", coil_id)
            session.rollback()
            return False
        finally:
            session.close()

    def archive_coil(self, coil_id: int) -> Optional[Coil]:
        """Архивировать катушку."""
        return self.update_coil(coil_id, archived=True)

    def unarchive_coil(self, coil_id: int) -> Optional[Coil]:
        """Разархивировать катушку."""
        return self.update_coil(coil_id, archived=False)

    def adjust_coil_remains(self, coil_id: int, new_remains: float,
                             notes: Optional[str] = None) -> Optional[Coil]:
        """Ручная корректировка остатка катушки с записью в историю."""
        session = self.get_session()
        try:
            coil = session.get(Coil, coil_id)
            if not coil:
                return None

            old_remains = coil.remains or 0
            diff = old_remains - new_remains  # Положительное = списание

            # Записываем в историю
            history = SpoolHistory(
                coil_id=coil_id,
                task_id=None,
                used_weight=diff,
                notes=notes or "Ручная корректировка",
            )
            session.add(history)

            coil.remains = new_remains
            session.commit()
            session.refresh(coil)
            return coil
        finally:
            session.close()

    # === SpoolHistory helpers ===

    def add_spool_history(self, coil_id: int, used_weight: float,
                          task_id: Optional[int] = None, notes: Optional[str] = None) -> SpoolHistory:
        """Добавить запись в историю расхода."""
        session = self.get_session()
        try:
            history = SpoolHistory(
                coil_id=coil_id,
                task_id=task_id,
                used_weight=used_weight,
                notes=notes,
            )
            session.add(history)
            session.commit()
            session.refresh(history)
            return history
        finally:
            session.close()

    def get_spool_history(self, coil_id: Optional[int] = None,
                          task_id: Optional[int] = None, limit: int = 100):
        """Получить историю расхода с фильтрами."""
        session = self.get_session()
        try:
            query = (
                session.query(SpoolHistory)
                .options(joinedload(SpoolHistory.task))
                .order_by(SpoolHistory.timestamp.desc())
            )
            if coil_id is not None:
                query = query.filter(SpoolHistory.coil_id == coil_id)
            if task_id is not None:
                query = query.filter(SpoolHistory.task_id == task_id)
            return query.limit(limit).all()
        finally:
            session.close()

    def delete_spool_history(self, history_id: int) -> bool:
        """Удалить запись из истории."""
        session = self.get_session()
        try:
            history = session.get(SpoolHistory, history_id)
            if not history:
                return False
            session.delete(history)
            session.commit()
            return True
        finally:
            session.close()

    def deduct_material(self, coil_id: int, amount: float, task_id: Optional[int] = None,
                        notes: Optional[str] = None) -> Optional[Coil]:
        """Списать материал с катушки (автоматическое при завершении задачи)."""
        session = self.get_session()
        try:
            coil = session.get(Coil, coil_id)
            if not coil:
                return None

            # Записываем в историю
            history = SpoolHistory(
                coil_id=coil_id,
                task_id=task_id,
                used_weight=amount,
                notes=notes or "Автосписание при завершении задачи",
            )
            session.add(history)

            # Обновляем остаток
            old_remains = coil.remains or 0
            coil.remains = max(0, old_remains - amount)
            coil.last_used = datetime.now(timezone.utc)

            # Если первое использование не установлено
            if not coil.first_used:
                coil.first_used = datetime.now(timezone.utc)

            # Автоматическое архивирование если кончился филамент
            if coil.remains <= 0:
                coil.archived = True

            session.commit()
            session.refresh(coil)
            return coil
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
            project = session.get(Project, project_id)
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
            project = session.get(Project, project_id)
            if not project:
                return False
            try:
                session.delete(project)
                session.commit()
                return True
            except SQLAlchemyError:
                logger.exception("Ошибка удаления проекта id=%s", project_id)
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
            return session.get(Project, project_id)
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
            task = session.get(Task, task_id)
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
            task = session.get(Task, task_id)
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
            return session.get(
                Task, task_id,
                options=[
                    joinedload(Task.project),
                    joinedload(Task.printer),
                    joinedload(Task.coil).joinedload(Coil.material),
                ],
            )
        finally:
            session.close()

    def get_tasks_by_status(self, statuses: List[str]) -> List[Task]:
        """Получить задачи с указанными статусами."""
        session = self.get_session()
        try:
            return (
                session.query(Task)
                .options(
                    joinedload(Task.project),
                    joinedload(Task.printer),
                    joinedload(Task.coil).joinedload(Coil.material),
                )
                .filter(Task.status.in_(statuses))
                .all()
            )
        finally:
            session.close()

    @staticmethod
    def _filter_model_kwargs(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
        valid_keys = {column.name for column in model_cls.__table__.columns}
        return {key: value for key, value in data.items() if key in valid_keys}

    # === Maintenance helpers ===

    def init_maintenance_types(self):
        """Инициализация типов обслуживания при первом запуске."""
        session = self.get_session()
        try:
            existing = session.query(MaintenanceType).count()
            if existing == 0:
                for mt_data in DEFAULT_MAINTENANCE_TYPES:
                    mt = MaintenanceType(**mt_data)
                    session.add(mt)
                session.commit()
        finally:
            session.close()

    def get_maintenance_types(self):
        """Получить все типы обслуживания."""
        session = self.get_session()
        try:
            return session.query(MaintenanceType).all()
        finally:
            session.close()

    def update_maintenance_type(self, type_id: int, **kwargs) -> Optional[MaintenanceType]:
        """Обновить интервал или описание типа обслуживания."""
        session = self.get_session()
        try:
            mt = session.get(MaintenanceType, type_id)
            if not mt:
                return None
            for key, value in kwargs.items():
                if hasattr(mt, key):
                    setattr(mt, key, value)
            session.commit()
            session.refresh(mt)
            return mt
        finally:
            session.close()

    def add_maintenance_record(self, printer_id: int, maintenance_type_id: int,
                                notes: Optional[str] = None, is_forced: bool = False) -> MaintenanceRecord:
        """Добавить запись о выполненном обслуживании."""
        session = self.get_session()
        try:
            printer = session.get(Printer, printer_id)
            if not printer:
                raise ValueError(f"Принтер {printer_id} не найден")

            record = MaintenanceRecord(
                printer_id=printer_id,
                maintenance_type_id=maintenance_type_id,
                performed_at=datetime.now(timezone.utc),
                print_hours_at=printer.print_hours or 0.0,
                notes=notes,
                is_forced=is_forced,
            )
            session.add(record)
            session.commit()
            # Перезагружаем с joinedload для lazy-атрибутов
            record = (
                session.query(MaintenanceRecord)
                .options(
                    joinedload(MaintenanceRecord.printer),
                    joinedload(MaintenanceRecord.maintenance_type),
                )
                .filter(MaintenanceRecord.id == record.id)
                .one()
            )
            session.expunge(record)
            return record
        finally:
            session.close()

    def get_maintenance_records(self, printer_id: Optional[int] = None, limit: int = 100):
        """Получить записи обслуживания с опциональным фильтром по принтеру."""
        session = self.get_session()
        try:
            query = (
                session.query(MaintenanceRecord)
                .options(
                    joinedload(MaintenanceRecord.printer),
                    joinedload(MaintenanceRecord.maintenance_type),
                )
                .order_by(MaintenanceRecord.performed_at.desc())
            )
            if printer_id is not None:
                query = query.filter(MaintenanceRecord.printer_id == printer_id)
            return query.limit(limit).all()
        finally:
            session.close()

    def delete_maintenance_record(self, record_id: int) -> bool:
        """Удалить запись обслуживания."""
        session = self.get_session()
        try:
            record = session.get(MaintenanceRecord, record_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True
        finally:
            session.close()

    def get_last_maintenance(self, printer_id: int, maintenance_type_id: int) -> Optional[MaintenanceRecord]:
        """Получить последнюю запись обслуживания определённого типа для принтера."""
        session = self.get_session()
        try:
            return (
                session.query(MaintenanceRecord)
                .filter_by(printer_id=printer_id, maintenance_type_id=maintenance_type_id)
                .order_by(MaintenanceRecord.performed_at.desc())
                .first()
            )
        finally:
            session.close()

    def ensure_printer_maintenance_records(self, printer_id: int):
        """Создать начальные записи обслуживания для принтера если их нет."""
        session = self.get_session()
        try:
            printer = session.get(Printer, printer_id)
            if not printer:
                return

            types = session.query(MaintenanceType).all()
            for mt in types:
                existing = (
                    session.query(MaintenanceRecord)
                    .filter_by(printer_id=printer_id, maintenance_type_id=mt.id)
                    .first()
                )
                if not existing:
                    record = MaintenanceRecord(
                        printer_id=printer_id,
                        maintenance_type_id=mt.id,
                        performed_at=datetime.now(timezone.utc),
                        print_hours_at=printer.print_hours or 0.0,
                        notes="Начальная инициализация",
                        is_forced=False,
                    )
                    session.add(record)
            session.commit()
        finally:
            session.close()

    def ensure_all_printers_maintenance(self):
        """Создать записи обслуживания для всех принтеров у которых их нет."""
        session = self.get_session()
        try:
            printers = session.query(Printer).all()
            for printer in printers:
                self.ensure_printer_maintenance_records(printer.id)
        finally:
            session.close()

    def get_printer_maintenance_status(self, printer_id: int) -> Dict[str, Any]:
        """Получить статус обслуживания принтера."""
        session = self.get_session()
        try:
            printer = session.get(Printer, printer_id)
            if not printer:
                return {}

            types = session.query(MaintenanceType).all()
            status_list = []
            needs_maintenance = False

            for mt in types:
                last_record = (
                    session.query(MaintenanceRecord)
                    .filter_by(printer_id=printer_id, maintenance_type_id=mt.id)
                    .order_by(MaintenanceRecord.performed_at.desc())
                    .first()
                )

                if last_record:
                    hours_since = (printer.print_hours or 0.0) - last_record.print_hours_at
                    performed_at = last_record.performed_at.isoformat() if last_record.performed_at else None
                else:
                    hours_since = printer.print_hours or 0.0
                    performed_at = None

                hours_remaining = mt.interval_hours - hours_since
                is_overdue = hours_remaining <= 0

                if is_overdue:
                    needs_maintenance = True

                status_list.append({
                    'type_id': mt.id,
                    'type_code': mt.code,
                    'type_name': mt.name,
                    'interval_hours': mt.interval_hours,
                    'last_performed_at': performed_at,
                    'hours_since_last': round(hours_since, 1),
                    'hours_remaining': round(hours_remaining, 1),
                    'is_overdue': is_overdue,
                })

            return {
                'printer_id': printer.id,
                'printer_name': printer.name,
                'print_hours': round(printer.print_hours or 0.0, 1),
                'maintenance_status': status_list,
                'needs_maintenance': needs_maintenance,
            }
        finally:
            session.close()
