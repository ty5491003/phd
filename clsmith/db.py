import datetime
import sqlalchemy as sql

from contextlib import contextmanager
from labm8 import system
from labm8 import fs
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError

Base = declarative_base()

# must call init() first
make_session = None

def init(path: str):
    """ must be called before using anything """
    global make_session
    path = fs.path(path)
    engine = sql.create_engine('sqlite:///{path}'.format(**vars()))
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    make_session = sql.orm.sessionmaker(bind=engine)


@contextmanager
def Session():
    """Provide a transactional scope around a series of operations."""
    session = make_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


# Database Schema


class Program(Base):
    """ CLSmith programs """
    __tablename__ = 'Programs'
    id = sql.Column(sql.String(40), primary_key=True)
    date = sql.Column(sql.DateTime, default=datetime.datetime.utcnow)

    # additional flags passed to CLSmith
    flags = sql.Column(sql.Text, nullable=False)

    # time taken to produce program (in seconds).
    runtime = sql.Column(sql.Float, nullable=False)

    # production output
    stdout = sql.Column(sql.Text, nullable=False)
    stderr = sql.Column(sql.Text, nullable=False)
    src = sql.Column(sql.Text, nullable=False)

    def __repr__(self):
        return self.id


class Testbed(Base):
    """ devices """
    __tablename__ = 'Testbeds'
    id = sql.Column(sql.Integer, primary_key=True)
    hostname = sql.Column(sql.String(63), nullable=False)  # RFC 1035
    platform = sql.Column(sql.String(255), nullable=False)  # CL_DEVICE_NAME
    device = sql.Column(sql.String(255), nullable=False)  # CL_PLATFORM_NAME
    __table_args__ = (sql.UniqueConstraint('hostname', 'platform', 'device', name='_uid'),)

    def __repr__(self):
        return "Host: {self.hostname}, Platform: {self.platform}, Device: {self.device}".format(**vars())


class Params(Base):
    """ params """
    __tablename__ = "Parameters"
    id = sql.Column(sql.Integer, primary_key=True)
    gsize_x = sql.Column(sql.Integer, nullable=False)
    gsize_y = sql.Column(sql.Integer, nullable=False)
    gsize_z = sql.Column(sql.Integer, nullable=False)
    lsize_x = sql.Column(sql.Integer, nullable=False)
    lsize_y = sql.Column(sql.Integer, nullable=False)
    lsize_z = sql.Column(sql.Integer, nullable=False)


class Result(Base):
    __tablename__ = "Results"
    id = sql.Column(sql.Integer, primary_key=True)
    program_id = sql.Column(sql.String(40), sql.ForeignKey("Programs.id"))
    device_id = sql.Column(sql.Integer, sql.ForeignKey("Devices.id"))
    date = sql.Column(sql.DateTime, default=datetime.datetime.utcnow)
    cli = sql.Column(sql.Text, nullable=False)
    status = sql.Column(sql.Integer, nullable=False)
    runtime = sql.Column(sql.Float, nullable=False)
    stdout = sql.Column(sql.Text, nullable=False)
    stderr = sql.Column(sql.Text, nullable=False)


# Helper functions


def get_testbed(platform_name: str, device_name: str) -> Testbed:
    return Testbed(hostname=system.HOSTNAME,
                   platform=platform_name,
                   device=device_name)


def register_testbed(platform_name: str, device_name: str) -> int:
    """
    Returns:
        int: Testbed ID.
    """
    new = False
    try:
        with Session() as session:
            d = get_testbed(platform_name, device_name)
            session.add(d)
            new = True
    except IntegrityError:
        with Session() as session:
            d = get_testbed(platform_name, device_name)
            assert(session.query(Testbed).filter(
                Testbed.hostname == d.hostname,
                Testbed.platform == d.platform,
                Testbed.device == d.device).count() == 1)

    with Session() as session:
        d = get_testbed(platform_name, device_name)
        testbed_id = session.query(Testbed).filter(
            Testbed.hostname == d.hostname,
            Testbed.platform == d.platform,
            Testbed.device == d.device).one().id

    if new:
        print("registered new testbed", testbed_id)

    return testbed_id
