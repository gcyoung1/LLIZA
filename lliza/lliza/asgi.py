"""
ASGI config for lliza project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from lliza import consumers

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lliza.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            [
                path("conversation-relay/", consumers.ConversationRelayConsumer.as_asgi()),
            ]
        )
    ),
})
