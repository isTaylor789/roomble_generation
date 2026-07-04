from src.controllers.generation import router as generation_router


def register_routers(app):
    app.include_router(generation_router)




