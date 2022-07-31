import pytest
import sqlalchemy as sa
import sqlalchemy.orm
from managed_service_fixtures import CockroachDetails
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@sa.orm.as_declarative()
class Base:
    id = sa.Column(sa.Integer, primary_key=True)


class User(Base):
    __tablename__ = "user"
    name = sa.Column(sa.String)
    todos = sa.orm.relationship("Todo", back_populates="user")


class Todo(Base):
    __tablename__ = "todo"
    title = sa.Column(sa.String)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"))
    user = sa.orm.relationship("User", back_populates="todos")


@pytest.fixture(scope="session", autouse=True)
def configure_db(managed_cockroach: CockroachDetails):
    if managed_cockroach.is_manager:
        engine = sa.create_engine(managed_cockroach.sync_dsn)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)
        engine.dispose()


async def test_cockroach(managed_cockroach: CockroachDetails):
    engine = create_async_engine(managed_cockroach.async_dsn)
    LocalSession = sa.orm.sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=True,
    )
    async with LocalSession() as session:
        user = User(name="test-user")
        todo = Todo(title="test-todo", user=user)
        session.add(user)
        session.add(todo)
        await session.commit()

    async with LocalSession() as session:
        statement = sa.select(User).options(sa.orm.selectinload(User.todos))
        results = await session.execute(statement)
        user = results.scalars().first()

    assert user.name == "test-user"
    assert user.todos[0].title == "test-todo"
