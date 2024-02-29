# chamaZetu api/Backend

This project is an api for chamaZetu application. It is built using FastAPI and PostgreSQL/SQLAlchemy/Supabase.

# MODELS & RELATIONSHIPS

```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_transactions = relationship('Transaction', back_populates='user')

class Chama(Base):
    __tablename__ = 'chamas'
    id = Column(Integer, primary_key=True)
    user_transactions = relationship('Transaction', back_populates='chama')

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    chama_id = Column(Integer, ForeignKey('chamas.id'))

    # Defining the relationships
    user = relationship('User', back_populates='user_transactions')
    chama = relationship('Chama', back_populates='user_transactions')
```

user = relationship("User", back_populates="user_transactions"): This line is defining a relationship between the current model (let's say it's Transaction) and the User model. The back_populates parameter is used to establish a bi-directional relationship. It means that when you load a Transaction, SQLAlchemy will also load the associated User object. On the User model, there should be a user_transactions attribute that refers back to the Transaction model.

chama = relationship("Chama", back_populates="user_transactions"): This line is doing the same thing as the first, but with a Chama model instead of a User model. It's establishing a relationship between the Transaction and Chama models, with user_transactions as the attribute on the Chama model that refers back to the Transaction model.
The value passed to back_populates is not the table name. It's the name of the attribute that should be added to the related model, which will refer back to the model on which relationship is being called.

In your case, user_transactions should be an attribute on both the User and Chama models that refers back to the model where this relationship is defined. This attribute is used to access the related records from an instance of the User or Chama model.
