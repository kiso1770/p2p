from aiogram.fsm.state import State, StatesGroup


class CreateFilter(StatesGroup):
    choosing_currency = State()
    choosing_side = State()
    entering_name = State()


class EditFilter(StatesGroup):
    main = State()              # main editor screen
    amount_min = State()        # 2-step range: enter min
    amount_max = State()        # then max
    price_min = State()
    price_max = State()
    experience = State()        # experience sub-screen
    min_trades = State()
    min_rate = State()
    description = State()       # description sub-screen
    whitelist = State()
    blacklist = State()
    sort = State()              # sort sub-screen
    orders_count = State()
    refresh_interval = State()
