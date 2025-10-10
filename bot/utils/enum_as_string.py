from sqlalchemy import TypeDecorator, String


class EnumAsString(TypeDecorator):
    impl = String(50)

    def __init__(self, enumtype, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(self, value, dialect):
        # When saving to DB
        if isinstance(value, self._enumtype):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        # When loading from DB
        if value is not None:
            return self._enumtype(value)
        return value