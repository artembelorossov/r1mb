from aiogram.fsm.state import State, StatesGroup


class AddLotStates(StatesGroup):
    waiting_photo = State()
    waiting_number = State()
    waiting_title = State()
    waiting_description = State()
    waiting_start_price = State()
