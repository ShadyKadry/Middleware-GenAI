from enum import Enum

# determines all available roles which are considered in the middleware application
class AccessRoles(Enum):
    # Note: values must match the values in ./templates/app.html
    ADMIN = "Admin"
    USER = "User"
    GUEST = "Guest"
    STUDENT = "Student"