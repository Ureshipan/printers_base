from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

Base = declarative_base()

class Printer(Base):
    __tablename__ = 'printers'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    last_service = Column(String)

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

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    desc = Column(Text)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    printer_id = Column(Integer, ForeignKey('printers.id'))
    coil_id = Column(Integer, ForeignKey('coils.id'))
    material_amount = Column(Float)
    project_id = Column(Integer, ForeignKey('projects.id'))
    time_start = Column(String)
    time_end = Column(String)
    progress = Column(Integer)
    model_gcode = Column(Text)

    printer = relationship('Printer')
    coil = relationship('Coil')
    project = relationship('Project')

class DBModel:
    def __init__(self, db_path='database.db'):
        self.db_path = db_path
        db_exists = os.path.exists(self.db_path)
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        if not db_exists:
            Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def add_printer(self, name, last_service=None):
        session = self.get_session()
        printer = Printer(name=name, last_service=last_service)
        session.add(printer)
        session.commit()
        session.close()
        return printer

    def add_material(self, name, nozzle_tmp, table_tmp):
        session = self.get_session()
        material = Material(name=name, nozzle_tmp=nozzle_tmp, table_tmp=table_tmp)
        session.add(material)
        session.commit()
        session.close()
        return material

    def add_coil(self, name, material_id, remains):
        session = self.get_session()
        coil = Coil(name=name, material_id=material_id, remains=remains)
        session.add(coil)
        session.commit()
        session.close()
        return coil

    def add_project(self, name, desc):
        session = self.get_session()
        project = Project(name=name, desc=desc)
        session.add(project)
        session.commit()
        session.close()
        return project

    def add_task(self, printer_id, coil_id, material_amount, project_id, time_start, time_end, progress, model_gcode):
        session = self.get_session()
        task = Task(printer_id=printer_id, coil_id=coil_id, material_amount=material_amount, 
                    project_id=project_id, time_start=time_start, time_end=time_end, progress=progress, model_gcode=model_gcode)
        session.add(task)
        session.commit()
        session.close()
        return task

    def get_printers(self):
        session = self.get_session()
        printers = session.query(Printer).all()
        session.close()
        return printers

    def get_materials(self):
        session = self.get_session()
        materials = session.query(Material).all()
        session.close()
        return materials

    def get_coils(self):
        session = self.get_session()
        coils = session.query(Coil).all()
        session.close()
        return coils

    def get_projects(self):
        session = self.get_session()
        projects = session.query(Project).all()
        session.close()
        return projects

    def get_tasks(self):
        session = self.get_session()
        tasks = session.query(Task).all()
        session.close()
        return tasks
