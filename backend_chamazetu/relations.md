# one-to-many relationships in SQLAlchemy

say we have two tables: Owner and Pet.

```python
class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(250), nullable=False)
```

```python
class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
```

If you want to add a one to many relationship between `owner` and `pet`. You should add a relationship to the parent class (`Owner` in this case) and name it `pets`. This is done using the `relationship` function from the `sqlalchemy.orm` module.

```python
class Owner(Base):
    __tablename__ = "owners"

    ...
    pets = relationship("Pet", back_populates="owner")
```

- `pets` is the name of the relationship but also the tablename name of the related model.
- `Pets` is the class name of the related model.
- `back_populates` says I am putting a new column in the child class `Pet` and I want to call it owner.

**I want to then add a new column to the `Pet` class, a foreign key referencing the parent `Owner` class.**

```python
class Pet(Base):
    __tablename__ = "pets"

    ...
    owner_id = Column(Integer, ForeignKey("owners.id"))
    owner = relationship("Owner", back_populates="pets")
```

**With this, i can populate the Owner class and then populate the Pet class, while setting the owner of the pet in the entry, the relationship will be automatically created and we can see the column that reference the relationship by highlighting the id.**
With this modification, you've explicitly defined the reverse relationship for both the `Owner` and `Pet` classes. Now, you can access the owner of a pet using `pet.owner` and the pets of an owner using `owner.pets`. This provides you with more explicit control over the names of the attributes representing the relationships on both sides.

---

---

# many-to-many relationships in SQLAlchemy

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)

```

```python
class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
```

To create a many-to-many relationship between `User` and `Channel`, you need to create an association table that links the two tables together. This table will have foreign keys to both `User` and `Channel` tables.

In the association table, define two columns, each with a foreign key to the primary key of the tables you want to link. Then, define a relationship in each of the two tables that points to the other table through the association table. (You can have other columns in the association table if you need to store additional information about the relationship.)

### association table

```python
user_channel = Table(
    "user_channel",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("channel_id", Integer, ForeignKey("channels.id")),
)
```

### User class

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    channels = relationship("Channel", secondary=user_channel, back_populates="users")
```

### Channel class

```python
class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    users = relationship("User", secondary=user_channel, back_populates="channels")
```

`user_channel` defines the association table that establishes the many-to-many relationship between `users` and `channels`.
Both `User` and `Channel` classes have a relationship defined using the secondary parameter to point to the association table.
`back_populates` is used to specify the reverse relationship between `User` and `Channel` classes, ensuring that changes to one side of the relationship are reflected on the other side.

Accessing Relationships:
You can access related objects through the defined relationships.

python
Copy code

### Access channels of a user

```python
user = session.query(User).first()
channels_of_user = user.channels
```

### Access users of a channel

```python
channel = session.query(Channel).first()
users_in_channel = channel.users
```

---

---

let's go through each `relationship` statement:

```python
member_chama = Table(
    "member_chama",
    Base.metadata,
    Column("member_id", Integer, ForeignKey("members.id")),
    Column("chama_id", Integer, ForeignKey("chamas.id")),
)


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    # for manager to assign an assistant # TODO: add this to the managers dashboard-they can assign already existing members to be staff
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # defining the relationship to chama
    chamas = relationship(
        "Chama", secondary=member_chama, back_populates="members", lazy="dynamic"
    )
    transaction_sent = relationship(
        "Transaction", back_populates="sender", foreign_keys="Transaction.sender_id"
    )
    transaction_received = relationship(
        "Transaction",
        back_populates="recepient",
        foreign_keys="Transaction.recepient_id",
    )
```

1. `chamas = relationship("Chama", secondary=member_chama, back_populates="members", lazy="dynamic")` in `Member` class:

   This establishes a many-to-many relationship between `Member` and `Chama` through the association table `member_chama`. The `back_populates` parameter sets up a bi-directional relationship, so accessing `chamas` from a `Member` instance will give all `Chama` instances associated with that member. The `lazy="dynamic"` means that the `Chama` instances are not loaded until they are accessed. This is correct if there is a `members` attribute in `Chama` model referring back to `Member`.

2. `transaction_sent = relationship("Transaction", back_populates="sender", foreign_keys="Transaction.sender_id")` and `transaction_received = relationship("Transaction", back_populates="recepient", foreign_keys="Transaction.recepient_id")` in `Member` class:

   These establish one-to-many relationships between `Member` and `Transaction`. A member can send many transactions and receive many transactions. The `foreign_keys` parameter is used to specify which foreign key on `Transaction` should be used for this relationship. These are correct if there are `sender` and `recepient` attributes in `Transaction` model referring back to `Member`.

```python
class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    # for manager to assign an assistant # TODO: add this to the managers dashboard-they can assign already existing members to be staff
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # defining relationship to transaction
    chamas = relationship("Chama", back_populates="manager")
```

3. `chamas = relationship("Chama", back_populates="manager")` in `Manager` class:

   This establishes a one-to-many relationship between `Manager` and `Chama`. A manager can manage many chamas. This is correct if there is a `manager` attribute in `Chama` model referring back to `Manager`.

```python
class Chama(Base):
    __tablename__ = "chamas"

    id = Column(Integer, primary_key=True)
    chamaname = Column(String(100), nullable=False, unique=True, index=True)
    manage_id = Column(Integer, ForeignKey("managers.id"))
    member_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=True)  # blue checkmark for legacy groups
    description = Column(String(250), nullable=False)

    # defining the relationship to user
    members = relationship(
        "Member", secondary=member_chama, back_populates="chamas", lazy="dynamic"
    )
    manager = relationship("Manager", back_populates="chamas")
    transactions = relationship("Transaction", back_populates="recepient")
```

4. `members = relationship("Member", secondary=member_chama, back_populates="chamas", lazy="dynamic")` in `Chama` class:

   This is the other side of the many-to-many relationship between `Member` and `Chama`. This is correct if there is a `chamas` attribute in `Member` model referring back to `Chama`.

5. `manager = relationship("Manager", back_populates="chamas")` in `Chama` class:

   This is the other side of the one-to-many relationship between `Manager` and `Chama`. This is correct if there is a `chamas` attribute in `Manager` model referring back to `Chama`.

6. `transactions = relationship("Transaction", back_populates="recepient")` in `Chama` class:

   This establishes a one-to-many relationship between `Chama` and `Transaction`. A chama can receive many transactions. This is correct if there is a `recepient` attribute in `Transaction` model referring back to `Chama`.

```python
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    sender = relationship(
        "Member", back_populates="transaction_sent", foreign_keys=[sender_id]
    )
    recepient_id = Column(Integer, ForeignKey("chamas.id"), nullable=False)
    recepient = relationship("Chama", back_populates="transactions")
    amount = Column(Integer, nullable=False)
    sent_at = Column(DateTime, default=datetime.now)
    is_reversed = Column(Boolean, default=False)
```

7. `sender = relationship("Member", back_populates="transaction_sent", foreign_keys=[sender_id])` and `recepient = relationship("Chama", back_populates="transactions")` in `Transaction` class:

   These establish many-to-one relationships from `Transaction` to `Member` and `Chama`. A transaction has one sender and one recipient. These are correct if there are `transaction_sent` attribute in `Member` model and `transactions` attribute in `Chama` model referring back to `Transaction`.

In summary, the relationships seem to be correctly defined, assuming the `back_populates` attributes exist on the related models.
