# Plugin entrypoint — see akuzoi_ai/plugin.py for implementation
# Explicit re-exports so MCDR can discover the lifecycle functions
from akuzoi_ai.plugin import (
    on_load as on_load,
    on_unload as on_unload,
    on_player_joined as on_player_joined,
    on_player_left as on_player_left,
    on_user_info as on_user_info,
)
