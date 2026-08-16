import math

from include.highlighting import debug_print
from include.pathfinding_logics import bfs_distances_from
from include.zustand import Gem, Zustand


def to_normal_koords(binary_koords: str):
    """Wandelt Binäre Koordinaten in einen Tuple um"""
    if len(binary_koords) != 12:
        raise ValueError(f"Wrong Binary input: {binary_koords}")
    else:
        decimal = int(binary_koords, 2)

        # 1 abziehen, um auf eine 0-basierte Welt zu wechseln
        decimal_adjusted = decimal - 1

        y = (decimal_adjusted // 91) + 1
        x = (decimal_adjusted % 91) + 1

        return (x, y)


def to_12_bit_koords(koords: tuple):
    """Wandelt eine Tuple-Koordinate in binär um"""
    if len(koords) != 2 or not (1 <= koords[0] < 92) or not (1 <= koords[1] < 46):
        raise ValueError(f"Wrong Koords input {koords}")
    decimal = (koords[1] - 1) * 91 + koords[0]
    binary_koords = put_zeros_infront_and_to_binary(decimal, 12)
    return binary_koords


def put_zeros_infront_and_to_binary(num: int, length: int):
    """Zu Binär und mit Nullen auf gewünschte Lnge auffüllen"""
    binary = ""  # binary result

    while num > 0:
        binary = str(num % 2) + binary
        num //= 2

    needed_zeros = length - len(binary)
    return needed_zeros * "0" + binary


def to_normal_offset(binary_offset: str):
    """Binären Offste in Tuple-Offset umwandeln"""
    if len(binary_offset) != 3:
        raise ValueError("Wrong Binary input")
    else:
        decimal = int(binary_offset, 2)
        offset_dict = {
            0: (0, 0),  # WAIT
            1: (1, 0),  # E
            2: (0, 1),  # S
            3: (-1, 0),  # W
            4: (0, -1),  # N
        }
        return offset_dict[decimal]


def read_team_buffer(zustand: Zustand):
    """Lesen des Teambuffers"""
    binary_buffer = zustand.team_buffer[:]
    offset_dict = {"WAIT": (0, 0), "E": (1, 0), "S": (0, 1), "W": (-1, 0), "N": (0, -1)}

    # Botpositionen lesen
    for i in range(4):
        if i == zustand.config.bot_id:
            bot_offset = offset_dict.get(zustand.last_move, (0, 0))
        else:
            bot_offset = to_normal_offset(binary_buffer[:3])
        binary_buffer = binary_buffer[3:]
        zustand.teammates[i] = (
            zustand.teammates[i][0] + bot_offset[0],
            zustand.teammates[i][1] + bot_offset[1],
        )

    got_request = False
    while True:
        if len(binary_buffer) < 2:
            zustand.bits_left = len(binary_buffer)
            break
        next_instruction = int(binary_buffer[:2], 2)
        binary_buffer = binary_buffer[2:]
        if next_instruction == 0:
            # Nachrichten alle vorbei
            zustand.bits_left = len(binary_buffer) + 2
            break
        elif next_instruction == 1:
            if binary_buffer[:3] == "010":
                got_request = True
            binary_buffer, msg = read_message(binary_buffer, zustand)
            if msg is not None:
                zustand.msgs_in_buffer.append(msg)
        elif next_instruction == 2:
            # Mapupdate is last thing in buffer
            read_map_update(zustand, binary_buffer)
            zustand.bits_left = len(binary_buffer) + 2
            break
        elif next_instruction == 3:
            # Gem-Update
            binary_buffer, msg = read_gem_update(binary_buffer, zustand)
            if msg is not None:
                zustand.msgs_in_buffer.append(msg)

    if got_request:
        zustand.is_there_an_open_request = True
    else:
        zustand.is_there_an_open_request = False

    # for i in range(4):
    #    debug_print(
    #        f"Teammate {i} pos: {zustand.teammates[i]}",
    #        zustand,
    #    )


def read_gem_update(binary_buffer: str, zustand: Zustand):
    """Lesen von Gem-relevanten Nachrichten"""
    msg_type = int(binary_buffer[:2], 2)
    msg = "11" + binary_buffer[:2]
    binary_buffer = binary_buffer[2:]
    if msg_type == 0:
        if msg + binary_buffer[:4] in zustand.msgs_written:
            # Delete msg
            full_msg = msg + binary_buffer[:4]
            binary_buffer = binary_buffer[4:]
            msg = ""
            zustand.msgs_written.remove(full_msg)
        else:
            msg += binary_buffer[:4]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            debug_print(f"Received gem channel reset {channel}", zustand)

            zustand.candidates[channel] = set()
            zustand.discovered_in_tick[channel] = -1
            zustand.gems_in_buffer = [
                gem for gem in zustand.gems_in_buffer if gem.channel != channel
            ]
            for r_gem in zustand.remembered_gems:
                if r_gem.channel == channel:
                    zustand.remembered_gems.remove(r_gem)
                    break
            if (
                len(zustand.approved_swarm_gem) > 0
                and zustand.approved_swarm_gem[1].channel == channel
            ):
                zustand.gems_and_nodes.pop(zustand.approved_swarm_gem[1].position, None)
                zustand.approved_swarm_gem = []

    elif msg_type == 1:
        if msg + binary_buffer[:30] in zustand.msgs_written:
            # Delete msg
            full_msg = msg + binary_buffer[:30]
            binary_buffer = binary_buffer[30:]
            msg = ""
            zustand.msgs_written.remove(full_msg)
        elif msg + binary_buffer[:54] in zustand.msgs_written:
            # Delete msg
            full_msg = msg + binary_buffer[:54]
            binary_buffer = binary_buffer[54:]
            msg = ""
            zustand.msgs_written.remove(full_msg)
        else:
            msg += binary_buffer[:30]
            position = to_normal_koords(binary_buffer[:12])
            binary_buffer = binary_buffer[12:]
            type_ = "swarm" if binary_buffer[0] == "1" else "regular"
            binary_buffer = binary_buffer[1:]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            taken = binary_buffer[0] == "1"
            binary_buffer = binary_buffer[1:]
            ttl = int(binary_buffer[:10], 2)
            binary_buffer = binary_buffer[10:]
            bot_id = int(binary_buffer[:2], 2)
            binary_buffer = binary_buffer[2:]

            if bot_id > zustand.config.bot_id:
                # Aus dem Tick davor
                ttl -= 1
            debug_print(
                f"Received new gem from Bot {bot_id}: Channel {channel}, Position {position}, Type {type_}, TTL {ttl}",
                zustand,
            )

            for gem in zustand.gems_in_buffer:
                if gem.channel == channel:
                    if gem.type_ == "swarm":
                        zustand.gems_and_nodes.pop(gem.position, None)
                    zustand.gems_in_buffer.remove(gem)
                    break

            nodes = []
            if type_ == "swarm":
                zustand.discovered_in_tick[channel] = zustand.tick - (
                    zustand.config.swarm_gem_ttl - ttl
                )
                for _ in range(3):
                    nodes.append(
                        get_pos_for_node_bin(binary_buffer[:8], position, zustand)
                    )
                    msg += binary_buffer[:8]
                    binary_buffer = binary_buffer[8:]
                debug_print(f"Got Nodes {nodes}", zustand)
                zustand.gems_and_nodes.update({position: nodes})
            else:
                zustand.discovered_in_tick[channel] = zustand.tick - (
                    zustand.config.gem_ttl - ttl
                )
            zustand.gems_in_buffer.append(
                Gem(position, ttl, type_, channel=channel, taken=taken, nodes=nodes)
            )

    elif msg_type == 2:
        if msg + binary_buffer[:38] in zustand.msgs_written:
            # Delete msg
            full_msg = msg + binary_buffer[:38]
            binary_buffer = binary_buffer[38:]
            msg = ""
            zustand.msgs_written.remove(full_msg)
        else:
            msg += binary_buffer[:14]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            ttl = int(binary_buffer[:10], 2)
            binary_buffer = binary_buffer[10:]
            nodes = []

            debug_print(
                f"Updating to swarm gem, channel: {channel}, ttl: {ttl}", zustand
            )
            for gem in zustand.gems_in_buffer:
                if gem.channel == channel:
                    gem.type_ = "swarm"
                    gem.ttl = ttl
                    for _ in range(3):
                        nodes.append(
                            get_pos_for_node_bin(
                                binary_buffer[:8], gem.position, zustand
                            )
                        )
                        msg += binary_buffer[:8]
                        binary_buffer = binary_buffer[8:]
                    debug_print(f"Got Nodes {nodes}", zustand)
                    gem.nodes = nodes
                    zustand.gems_and_nodes.update({gem.position: nodes})
                    break
    elif msg_type == 3:
        binary_buffer, msg = gem_taking(binary_buffer, zustand)

    return binary_buffer, msg


def gem_taking(binary_buffer: str, zustand: Zustand):
    """Nimmt Gem oder gibt ihn frei"""
    msg = "1111" + binary_buffer[:5]
    if msg in zustand.msgs_written:
        # Delete msg
        full_msg = msg
        binary_buffer = binary_buffer[5:]
        msg = ""
        zustand.msgs_written.remove(full_msg)
    else:
        if binary_buffer[:1] == "1":

            binary_buffer = binary_buffer[1:]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            debug_print(f"Received gem taking message for channel {channel}", zustand)
            for gem in zustand.gems_in_buffer:
                if gem.channel == channel:
                    gem.taken = True
                    break

        elif binary_buffer[:1] == "0":
            binary_buffer = binary_buffer[1:]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            debug_print(f"Received gem untaking message for channel {channel}", zustand)
            for gem in zustand.gems_in_buffer:
                if gem.channel == channel:
                    gem.taken = False
                    break

    return binary_buffer, msg


def read_message(binary_buffer: str, zustand: Zustand):
    """Lesen von Nachrichten"""
    msg_type = int(binary_buffer[:2], 2)
    msg = "01" + binary_buffer[:2]
    binary_buffer = binary_buffer[2:]
    if msg_type == 0:

        if msg + binary_buffer[:14] in zustand.msgs_written:
            # Delete msg
            zustand.msgs_written.remove(msg + binary_buffer[:14])
            binary_buffer = binary_buffer[14:]
            msg = ""
        else:
            msg += binary_buffer[:14]
            b_id = int(binary_buffer[:2], 2)
            binary_buffer = binary_buffer[2:]
            b_pos = to_normal_koords(binary_buffer[:12])
            binary_buffer = binary_buffer[12:]
            debug_print(f"Received message from Bot {b_id} at {b_pos}", zustand)
            zustand.teammates[b_id] = b_pos
    elif msg_type == 1:
        next_instruction = int(binary_buffer[:1], 2)
        msg += binary_buffer[:1]
        binary_buffer = binary_buffer[1:]
        if next_instruction == 0:
            if msg + binary_buffer[:4] in zustand.msgs_written:
                # Delete msg
                full_msg = msg + binary_buffer[:4]
                binary_buffer = binary_buffer[4:]
                msg = ""
                zustand.msgs_written.remove(full_msg)
            else:
                msg += binary_buffer[:4]
                channel = int(binary_buffer[:4], 2)
                binary_buffer = binary_buffer[4:]
                count = int(binary_buffer[:2], 2)
                binary_buffer = binary_buffer[2:]
                debug_print(
                    f"Received gem meet request Channel {channel}, Count {count}",
                    zustand,
                )
                if zustand.open_request and zustand.open_request_channel == channel:
                    debug_print(f"Was from me", zustand)
                    approval = handle_meet_request(zustand, count, channel)
                    return binary_buffer, approval

                for gem in zustand.gems_in_buffer:
                    if gem.channel == channel:
                        dist = zustand.distances_to_bot.get(gem.position, 1000)
                        if dist < zustand.weights.b_max_Swarm_gem_dist:
                            zustand.accepted_request = True
                            msg += put_zeros_infront_and_to_binary(count + 1, 2)
                        else:
                            zustand.accepted_request = False
                            msg += put_zeros_infront_and_to_binary(count, 2)
                        zustand.msgs_written.append(msg)
                        break
        else:
            if msg in zustand.msgs_written:
                # Delete msg
                zustand.msgs_written.remove(msg)
                msg = ""
            else:
                debug_print("Got alarm signal", zustand)
                zustand.alarmed = (True, zustand.tick)
    elif msg_type == 2:
        if msg + binary_buffer[:6] in zustand.msgs_written:
            # Delete msg
            full_msg = msg + binary_buffer[:6]
            binary_buffer = binary_buffer[6:]
            msg = ""
            zustand.msgs_written.remove(full_msg)
        else:
            msg += binary_buffer[:6]
            count = int(binary_buffer[:2], 2)
            binary_buffer = binary_buffer[2:]
            channel = int(binary_buffer[:4], 2)
            binary_buffer = binary_buffer[4:]
            debug_print(
                f"Received meet approval with count {count} and channel {channel}",
                zustand,
            )
            debug_print(f"Bin: {msg}", zustand)
            twin_gem = None
            for gem in zustand.gems_in_buffer:
                if gem.channel == channel:
                    twin_gem = gem
                    break
            if twin_gem is None:
                pass
            elif zustand.accepted_request and len(zustand.approved_swarm_gem) == 0:
                zustand.approved_swarm_gem = [
                    count + 1,
                    Gem(
                        twin_gem.position,
                        twin_gem.ttl,
                        "swarm",
                        channel,
                        twin_gem.nodes,
                    ),
                    zustand.tick,
                ]
            elif not zustand.accepted_request and len(zustand.approved_swarm_gem) == 0:
                zustand.approved_gem_channel = channel
            zustand.accepted_request = False
    elif msg_type == 3:
        if msg in zustand.msgs_written:
            # Delete msg
            zustand.msgs_written.remove(msg)
            msg = ""
        else:
            debug_print("Received Turn passing", zustand)
            zustand.turn -= 1
            if zustand.turn == -1:
                zustand.turn = 3
    return binary_buffer, msg


def write_pos_update(zustand: Zustand, pos: tuple):
    """Positions-Update schreiben"""
    pos_bin = to_12_bit_koords(pos)
    msg = "0100" + put_zeros_infront_and_to_binary(zustand.config.bot_id, 2) + pos_bin
    debug_print(
        f"Writing position update to buffer (Id: {zustand.config.bot_id}): {pos}",
        zustand,
    )
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write position update! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return
    zustand.bits_left -= len(msg)
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.teammates[zustand.config.bot_id] = pos


def send_swarm_gem_meet_request(zustand: Zustand, pos: tuple, channel: int):
    debug_print(
        f"Bot {zustand.config.bot_id} is sending swarm gem meet request for gem {pos}",
        zustand,
    )
    msg = "01010" + put_zeros_infront_and_to_binary(channel, 4) + "00"
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write Meet request! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return
    zustand.bits_left -= len(msg)
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.open_request = msg
    zustand.open_request_channel = channel


def send_alarm(zustand: Zustand):
    debug_print(
        f"Bot {zustand.config.bot_id} is sending alarm signal",
        zustand,
    )
    msg = "01011"
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write Alarm signal! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return
    zustand.bits_left -= len(msg)
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.open_request = msg


def check_for_alarm(zustand: Zustand):
    if zustand.approved_swarm_gem:
        dists = bfs_distances_from(
            zustand.approved_swarm_gem[1].position,
            zustand,
            [o["position"] for o in zustand.opponents],
        )
        if any(
            dists[o["position"]] <= zustand.weights.b_alarm_dist
            for o in zustand.opponents
        ):
            debug_print(
                f"Opponent is near the Swarmgem at {zustand.approved_swarm_gem[1].position}",
                zustand,
            )
            if not zustand.alarmed[0]:
                send_alarm(zustand)
            zustand.alarmed = (True, zustand.tick)
    else:
        zustand.alarmed = (False, 0)

    if (
        zustand.alarmed[0]
        and zustand.tick - zustand.alarmed[1] >= zustand.weights.b_alarm_duration
    ):
        debug_print(
            f"Alarm signal expired",
            zustand,
        )
        zustand.alarmed = (False, 0)

    if zustand.alarmed[0]:
        debug_print("🚨 Opponent is near the Swarmgem", zustand)


def send_swarm_gem_meet_approval(zustand: Zustand, count: int, channel: int):
    debug_print(
        f"Bot {zustand.config.bot_id} is sending swarm gem meet approval for count {count}",
        zustand,
    )
    msg = (
        "0110"
        + put_zeros_infront_and_to_binary(count, 2)
        + put_zeros_infront_and_to_binary(channel, 4)
    )
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write Meet approval! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return None
    zustand.bits_left -= len(msg)
    zustand.msgs_written.append(msg)
    return msg


def handle_meet_request(zustand: Zustand, count: int, channel: int):
    if count >= 2:
        debug_print(
            f"Awaited swarm gem meet request with count {count}, sending swarm gem approval",
            zustand,
        )
        twin_gem = None
        for gem in zustand.gems_in_buffer:
            if gem.channel == channel:
                twin_gem = gem
                break
        if twin_gem is None:
            approval = None
            zustand.open_request = ""
            zustand.open_request_channel = -1
            return approval
        approval = send_swarm_gem_meet_approval(zustand, count, channel)

        zustand.approved_swarm_gem = [
            count + 1,
            Gem(twin_gem.position, twin_gem.ttl, "swarm", channel, twin_gem.nodes),
            zustand.tick,
        ]
        zustand.open_request = ""
        zustand.open_request_channel = -1
    else:
        debug_print(
            f"Awaited swarm gem meet request with count {count}, not enough approvals yet.",
            zustand,
        )
        approval = None

    return approval


def find_swarm_gem_to_request(zustand: Zustand):
    """Schaut, ob es einen Swarmgem gibt, der sich lohnt"""
    if len(zustand.approved_swarm_gem) > 0:
        return
    if zustand.is_there_an_open_request:
        return
    if zustand.approved_gem_channel != -1:
        return
    possible_s_gems = []
    pos_and_dists = {}
    for gem in zustand.gems_in_buffer:
        if gem.type_ == "swarm":
            dists = bfs_distances_from(gem.position, zustand, zustand.teammates)
            count = 0
            if dists[zustand.bot] < zustand.weights.b_max_Swarm_gem_dist:
                count += 1
                for i in range(4):
                    if i == zustand.config.bot_id:
                        continue
                    if (
                        dists[zustand.teammates[i]]
                        < zustand.weights.b_max_Swarm_gem_dist
                    ):
                        count += 1
            if count >= 3:
                debug_print(
                    f"Found swarm gem at {gem.position} in buffer to send meet request for.",
                    zustand,
                )
                possible_s_gems.append(gem)
                pos_and_dists.update({gem.position: dists})
    if len(possible_s_gems) > 0:
        best_gem = None
        least_sum_dists = 10000
        for gem in possible_s_gems:
            dist_sum = 0
            for i in range(4):
                dist_sum += pos_and_dists[gem.position][zustand.teammates[i]]
            if dist_sum < least_sum_dists:
                least_sum_dists = dist_sum
                best_gem = gem

        send_swarm_gem_meet_request(zustand, best_gem.position, best_gem.channel)
        zustand.is_there_an_open_request = True


def pass_turn(zustand: Zustand):
    msg = "0111"
    debug_print("Passing Map writing", zustand)
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write pass! Bits left: {zustand.bits_left}",
            zustand,
        )
        return

    zustand.bits_left -= 4
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.turn -= 1
    if zustand.turn == -1:
        zustand.turn = 3


def write_map_update(zustand: Zustand):
    """Schreibt das Map-Update"""
    if zustand.turn == zustand.config.bot_id:
        # Write map Updates columnwise

        cols = []
        pos_count = 0
        for x in range(zustand.config.width):
            col = []
            for y in range(zustand.config.height):
                if (
                    zustand.shared_matrix[y][x] == "/"
                    and zustand.saved_matrix[y][x] != "/"
                ):
                    col.append((x, y))
                    pos_count += 1
            if len(col) > 0:
                cols.append(col)
        rows = []
        for y in range(zustand.config.height):
            row = []
            for x in range(zustand.config.width):
                if (
                    zustand.shared_matrix[y][x] == "/"
                    and zustand.saved_matrix[y][x] != "/"
                ):
                    row.append((x, y))
            if len(row) > 0:
                rows.append(row)

        if pos_count <= 4 and zustand.tick <= 200 or pos_count == 0:
            pass_turn(zustand)
            zustand.map_update = ""
            return

        types = {"/": "00", "0": "01", "X": "10"}
        # Columnwise:
        map_update_col_wise = "100"
        for i, col in enumerate(cols):
            map_update_col_wise += to_12_bit_koords(col[0])
            # add all points from start to last in col + shift
            x = col[0][0]
            for y in range(col[0][1], col[-1][1] + 1):
                map_update_col_wise += types[zustand.saved_matrix[y][x]]

            if i != len(cols) - 1:
                # Shift
                map_update_col_wise += "110"

        map_update_col_wise += "111"  # End

        map_update_row_wise = "101"
        for i, row in enumerate(rows):
            map_update_row_wise += to_12_bit_koords(row[0])
            # add all points from start to last in row + shift
            y = row[0][1]
            for x in range(row[0][0], row[-1][0] + 1):
                map_update_row_wise += types[zustand.saved_matrix[y][x]]

            if i != len(rows) - 1:
                # Shift
                map_update_row_wise += "110"

        map_update_row_wise += "111"  # End

        if len(map_update_col_wise) < len(map_update_row_wise):
            zustand.map_update = map_update_col_wise
            debug_print(f"🗺️ Writing Map Update col wise", zustand)
        else:
            zustand.map_update = map_update_row_wise
            debug_print(f"🗺️ Writing Map Update row wise", zustand)


def read_map_update(zustand: Zustand, binary_buffer):
    zustand.map_update = "10"
    type_ = binary_buffer[0]
    zustand.map_update += binary_buffer[0]
    binary_buffer = binary_buffer[1:]

    x, y = to_normal_koords(binary_buffer[:12])
    zustand.map_update += binary_buffer[:12]
    binary_buffer = binary_buffer[12:]
    points_read = 0
    while True:
        instruction = binary_buffer[:2]
        zustand.map_update += binary_buffer[:2]
        binary_buffer = binary_buffer[2:]
        if instruction == "11":
            instruction += binary_buffer[0]
            zustand.map_update += binary_buffer[0]
            binary_buffer = binary_buffer[1:]

        if instruction == "111":
            break
        elif instruction == "00":
            # /
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "01":
            zustand.saved_matrix[y][x] = "0"
            zustand.current_matrix[y][x] = "0"
            zustand.shared_matrix[y][x] = "0"
            points_read += 1
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "10":
            zustand.saved_matrix[y][x] = "X"
            zustand.current_matrix[y][x] = "X"
            zustand.shared_matrix[y][x] = "X"
            points_read += 1
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "110":
            # Shift
            x, y = to_normal_koords(binary_buffer[:12])
            zustand.map_update += binary_buffer[:12]
            binary_buffer = binary_buffer[12:]

    if points_read > 0:
        if points_read >= 8:
            zustand.bits_per_point.append(len(zustand.map_update) / points_read)
        debug_print(f"🗺️ Received map update with {points_read} points", zustand)
    else:
        zustand.map_update = ""


def check_team_buffer(zustand: Zustand):
    """Validiere die Gems, die über den Buffer eingespeichert wurden"""
    new_gems = []
    channels_to_clear = []
    for gem in zustand.gems_in_buffer:
        if zustand.distances_to_bot.get(gem.position) is None:
            channels_to_clear.append(gem.channel)
            debug_print(
                f"Gem at {gem.position} is in buffer but not reachable, clearing from buffer.",
                zustand,
            )
        elif gem.position in zustand.floors:
            # prüfen, ob das Gem noch in visible_gems ist
            is_still_there = False
            for visible_gem in zustand.visible_gems:
                if gem.position == visible_gem.position:
                    is_still_there = True
                    break
            if not is_still_there:
                channels_to_clear.append(gem.channel)
                debug_print(
                    f"Gem at {gem.position} is in buffer but not visible anymore, clearing from buffer.",
                    zustand,
                )
            else:
                new_gems.append(gem)
        else:
            dist = math.hypot(
                zustand.bot[0] - gem.position[0], zustand.bot[1] - gem.position[1]
            )
            from include.signal_interpreter import get_signal_from_gem

            signal = get_signal_from_gem(zustand, gem)
            if (
                dist < zustand.cutoff_dist
                and signal - 0.04 > zustand.config.signal_cutoff
                and zustand.signal_channels[gem.channel] == 0
            ):
                channels_to_clear.append(gem.channel)
                debug_print("Should have been a signal was none so no gem", zustand)
            else:
                if (
                    zustand.signal_channels[gem.channel] > 0
                    and dist < zustand.cutoff_dist
                ):

                    from include.signal_interpreter import (
                        get_candidates_for_signal,
                    )

                    if gem.type_ == "regular":
                        age = zustand.config.gem_ttl - gem.ttl
                    else:
                        age = zustand.config.swarm_gem_ttl - gem.ttl

                    if age > zustand.config.signal_fade:
                        candidates = get_candidates_for_signal(
                            zustand, get_signal_from_gem(zustand, gem), gem.channel
                        )
                        if gem.position in candidates:
                            new_gems.append(gem)
                        else:
                            channels_to_clear.append(gem.channel)
                            debug_print(
                                f"Gem at {gem.position} with ttl {gem.ttl} is in buffer but not in candidates {candidates} for signal, clearing from buffer.",
                                zustand,
                            )
                    else:
                        new_gems.append(gem)
                else:
                    new_gems.append(gem)

    for channel in channels_to_clear:
        remove_channel_from_buffer(channel, zustand)
        zustand.candidates[channel] = set()
        zustand.discovered_in_tick[channel] = -1
        for s_gem, tick in zustand.used_swarm_gems:
            if s_gem.channel == channel:
                zustand.used_swarm_gems.remove((s_gem, tick))

    zustand.gems_in_buffer = new_gems

    if zustand.approved_gem_channel != -1:
        channel = zustand.approved_gem_channel
        in_there = False
        for gem in zustand.gems_in_buffer:
            if gem.channel == channel:
                in_there = True
                break
        if not in_there:
            zustand.approved_gem_channel = -1
    if len(zustand.approved_swarm_gem) > 0 and zustand.approved_swarm_gem[
        1
    ].position not in [g.position for g in zustand.gems_in_buffer]:
        debug_print(
            f"Approved swarm gem at {zustand.approved_swarm_gem[1].position} is not in new gems list",
            zustand,
        )
        zustand.gems_and_nodes.pop(zustand.approved_swarm_gem[1].position, None)
        zustand.approved_swarm_gem = []

    if (
        len(zustand.approved_swarm_gem) > 0
        and zustand.approved_swarm_gem[2] + zustand.weights.b_max_swarm_gem_awaiting
        < zustand.tick
    ):
        debug_print(f"⚠️ Reducing Gem_approval Count", zustand)
        zustand.approved_swarm_gem[0] = zustand.approved_swarm_gem[0] - 1
        zustand.approved_swarm_gem[2] = (
            zustand.tick - zustand.weights.b_max_swarm_gem_awaiting + 50
        )
        if zustand.approved_swarm_gem[0] < 3:
            debug_print(f"⚠️ Deleting approved Gem, Took too long", zustand)
            for gem_b in zustand.gems_in_buffer:
                if gem_b.position == zustand.approved_swarm_gem[1].position:
                    gem_b.type_ = "regular"
                    zustand.gems_and_nodes.pop(
                        zustand.approved_swarm_gem[1].position, None
                    )
                    break
            for gem_r in zustand.remembered_gems:
                if gem_r.position == zustand.approved_swarm_gem[1].position:
                    gem_r.type_ = "regular"
                    zustand.gems_and_nodes.pop(
                        zustand.approved_swarm_gem[1].position, None
                    )
                    break

            zustand.approved_swarm_gem = []

    if zustand.bot != zustand.teammates[zustand.config.bot_id]:
        diff = (
            zustand.bot[0] - zustand.teammates[zustand.config.bot_id][0],
            zustand.bot[1] - zustand.teammates[zustand.config.bot_id][1],
        )
        debug_print(
            f"⚠️ Bot position {zustand.bot} does not match buffer position {zustand.teammates[zustand.config.bot_id]}, diff: {diff}!",
            zustand,
        )
        if abs(diff[0]) >= 1 or abs(diff[1]) >= 1:
            debug_print(
                "⚠️ Position difference is greater/equal than 1, resending position update.",
                zustand,
            )
            zustand.offset = True
            zustand.teammates[zustand.config.bot_id] = zustand.bot

    new_dict = {}
    for key, value in zustand.gems_and_nodes.items():
        if key in [g.position for g in zustand.gems_in_buffer]:
            new_dict.update({key: value})
    zustand.gems_and_nodes = new_dict


def set_team_buffer(zustand: Zustand):
    msg = []
    for i in range(32):
        byte = zustand.team_buffer[i * 8 : (i + 1) * 8]
        decimal = int(byte, 2)
        msg.append(decimal)
    # debug_print(
    #    f"Used {256 - (zustand.bits_left)} bits of 256 for msg and {len(zustand.map_update)} for 🗺️ ({(256 - zustand.bits_left + len(zustand.map_update)) / 256 * 100:.2f}%)",
    #    zustand,
    # )
    return msg


def write_offset_to_buffer(zustand: Zustand, next_field: tuple):
    bot_offset = (next_field[0] - zustand.bot[0], next_field[1] - zustand.bot[1])
    offset_dict = {
        (0, 0): "000",  # WAIT
        (1, 0): "001",  # E
        (0, 1): "010",  # S
        (-1, 0): "011",  # W
        (0, -1): "100",  # N
    }
    new_buffer = (
        zustand.team_buffer[: 3 * zustand.config.bot_id]
        + offset_dict[bot_offset]
        + zustand.team_buffer[3 * (zustand.config.bot_id + 1) :]
    )

    # Falls der nächste Bot dran ist, muss der Buffer für ihn auf 000 gesetzt werden,
    # damit wenn er abstürzt, kein Fehler passiert.
    next_bot_id = (zustand.config.bot_id + 1) % 4
    new_buffer = (
        new_buffer[: 3 * next_bot_id] + "000" + new_buffer[3 * (next_bot_id + 1) :]
    )
    zustand.team_buffer = new_buffer


def write_new_gem_msg(gem: Gem, zustand: Zustand):
    if gem.channel == -1:
        return

    debug_print(
        f"Attempting to write gem at {gem.position} to buffer, type {gem.type_}",
        zustand,
    )
    if gem.type_ == "swarm":
        zustand.gems_and_nodes.update({gem.position: gem.nodes})
    channel_to_clear = None
    status_of_gem = None
    for b_gem in zustand.gems_in_buffer:
        if gem.position == b_gem.position:
            # already in buffer
            status_of_gem = b_gem.taken
            debug_print(
                f"Gem at {b_gem.position} is already in buffer with type {b_gem.type_}",
                zustand,
            )
            b_gem.ttl = gem.ttl
            if gem.type_ == "swarm" and b_gem.type_ == "regular":
                # update regular to swarm
                debug_print(
                    f"Updating regular gem at {b_gem.position} to swarm gem in buffer.",
                    zustand,
                )
                update_to_swarm_gem(
                    b_gem.channel, gem.ttl, gem.position, gem.nodes, zustand
                )
            return

        elif gem.channel == b_gem.channel:
            debug_print(
                f"⚠️ Channel {b_gem.channel} is already occupied by gem at {b_gem.position}, clearing it from buffer to write new gem at {gem.position}.",
                zustand,
            )
            channel_to_clear = b_gem.channel
            break
    if channel_to_clear is not None:
        remove_channel_from_buffer(channel_to_clear, zustand)

    channel_bits = put_zeros_infront_and_to_binary(gem.channel, 4)
    _13bit = "0" if gem.type_ == "regular" else "1"
    if status_of_gem is not None and status_of_gem == True:
        taken_bit = "1"
    else:
        taken_bit = "0" if not gem.taken else "1"

    ttl_bits = put_zeros_infront_and_to_binary(gem.ttl, 10)
    bot_id = put_zeros_infront_and_to_binary(zustand.config.bot_id, 2)

    node_bits = ""
    if _13bit == "1":
        # Swarmgem
        for node in gem.nodes:
            node_bits += zustand.node_offset_to_bin[
                get_offset_for_node(node, gem.position)
            ]

        if len(node_bits) != 24:
            raise ValueError(f"Incorrect node bits length ({len(node_bits)})")

    gem_bits = str(
        "1101"
        + to_12_bit_koords(gem.position)
        + _13bit
        + channel_bits
        + taken_bit
        + ttl_bits
        + bot_id
        + node_bits
    )
    if zustand.bits_left < len(gem_bits):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write gem! Bits left: {zustand.bits_left}, needed: {len(gem_bits)}",
            zustand,
        )
        return

    zustand.bits_left -= len(gem_bits)
    zustand.msgs_in_buffer.append(gem_bits)
    zustand.msgs_written.append(gem_bits)
    if len(zustand.team_buffer) != 256:
        raise ValueError("Buffer length is not 256 bits after writing gem!")

    gem.taken = taken_bit == "1"
    zustand.gems_in_buffer.append(
        Gem(
            gem.position,
            gem.ttl,
            gem.type_,
            channel=gem.channel,
            nodes=gem.nodes,
            taken=gem.taken,
        )
    )


def precalculate_node_to_bin(zustand: Zustand):
    decimal_index = 0
    skipped = 0
    for y in range(-11, 12):
        for x in range(-11, 12):
            if x == 0 and y == 0:
                continue

            if abs(x) + abs(y) <= 11:
                if skipped < 8 and abs(x) + abs(y) == 11:
                    skipped += 1
                    continue
                else:
                    bin_index = put_zeros_infront_and_to_binary(decimal_index, 8)
                    zustand.node_offset_to_bin.update({(x, y): bin_index})
                    zustand.bin_to_node_offset.update({bin_index: (x, y)})
                    decimal_index += 1


def get_offset_for_node(node, gem_pos):
    return (node[0] - gem_pos[0], node[1] - gem_pos[1])


def get_pos_for_node_bin(bin_, gem_pos, zustand: Zustand):
    offset = zustand.bin_to_node_offset[bin_]
    return (gem_pos[0] + offset[0], gem_pos[1] + offset[1])


def gem_in_buffer(pos: tuple, zustand: Zustand):
    """Schaut, ob eine Position schon im Buffer ist"""
    for gem in zustand.gems_in_buffer:
        if pos == gem.position:
            return True
    return False


def update_to_swarm_gem(channel, ttl, gem_pos, nodes, zustand: Zustand):
    debug_print(f"Updating Channel {channel} to swarm gem", zustand)
    node_bits = ""
    for node in nodes:
        node_bits += zustand.node_offset_to_bin[get_offset_for_node(node, gem_pos)]
    if len(node_bits) != 24:
        raise ValueError(f"Incorrect node bits length ({len(node_bits)})")
    msg = (
        "1110"
        + put_zeros_infront_and_to_binary(channel, 4)
        + put_zeros_infront_and_to_binary(ttl, 10)
        + node_bits
    )
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write channel clear! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.bits_left -= len(msg)
    for gem in zustand.gems_in_buffer:
        if gem.channel == channel:
            gem.type_ = "swarm"
            break


def remove_channel_from_buffer(channel: int, zustand: Zustand):

    debug_print(
        f"[CLEAR_POS] target_channel={channel}",
        zustand,
    )
    msg = "1100" + put_zeros_infront_and_to_binary(channel, 4)
    if zustand.bits_left < len(msg):
        debug_print(
            f"⚠️ Not enough bits left in buffer to write channel clear! Bits left: {zustand.bits_left}, needed: {len(msg)}",
            zustand,
        )
        return
    zustand.msgs_in_buffer.append(msg)
    zustand.msgs_written.append(msg)
    zustand.bits_left -= 8
    for gem in zustand.gems_in_buffer:
        if gem.channel == channel:
            zustand.gems_in_buffer.remove(gem)
            if gem.type_ == "swarm":
                zustand.gems_and_nodes.pop(gem.position, None)
            break

    for r_gem in zustand.remembered_gems:
        if r_gem.channel == channel:
            zustand.remembered_gems.remove(r_gem)
            break

    if (
        len(zustand.approved_swarm_gem) > 0
        and zustand.approved_swarm_gem[1].channel == channel
    ):
        zustand.approved_swarm_gem = []

    if len(zustand.team_buffer) != 256:
        raise ValueError("Buffer length is not 256 bits after clearing position!")


def take_all_needed_gems(zustand: Zustand):
    for gem in zustand.gems_in_buffer:
        if not gem.taken and gem.type_ == "regular":
            nearest_bot = find_nearest_bot(gem.position, zustand)
            if nearest_bot == zustand.config.bot_id:
                debug_print(
                    f"Bot {zustand.config.bot_id} is taking gem at {gem.position} from buffer",
                    zustand,
                )
                take_gem_from_buffer(gem.position, zustand)


def find_nearest_bot(pos: tuple, zustand: Zustand):
    """BFS to find nearest bot to the gem position"""
    visited = set()
    queue = [pos]
    while queue:
        current_pos = queue.pop(0)
        if current_pos in visited:
            continue
        visited.add(current_pos)

        for bot_id, bot_pos in enumerate(zustand.teammates):
            if bot_pos == current_pos:
                return bot_id

        # Add neighbors to the queue
        neighbors = [
            (current_pos[0] + dx, current_pos[1] + dy)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
        ]
        for neighbor in neighbors:
            if (
                1 <= neighbor[0] < zustand.config.width
                and 1 <= neighbor[1] < zustand.config.height
                and neighbor not in visited
                and zustand.saved_matrix[neighbor[1]][neighbor[0]] != "X"
            ):
                queue.append(neighbor)


def take_gem_from_buffer(pos: tuple, zustand: Zustand):
    for gem in zustand.gems_in_buffer:
        if pos == gem.position:
            if not gem.taken:
                gem.taken = True
                zustand.gems_taken.append(gem)
                msg = "1111" + "1" + put_zeros_infront_and_to_binary(gem.channel, 4)
                if zustand.bits_left < len(msg):
                    debug_print(
                        f"⚠️ Not enough bits left in buffer to write gem taking message! Bits left: {zustand.bits_left}, needed: {len(msg)}",
                        zustand,
                    )
                    return
                zustand.bits_left -= len(msg)
                zustand.msgs_in_buffer.append(msg)
                zustand.msgs_written.append(msg)
            break


def check_taken_gems(zustand: Zustand):
    new_gems_taken = []
    for t_gem in zustand.gems_taken:
        for gem in zustand.gems_in_buffer:
            if t_gem.position == gem.position:
                # Actualize Type
                t_gem.type_ = gem.type_
        if t_gem.type_ == "swarm":
            untake_gem(t_gem.position, zustand)
        elif find_nearest_bot(t_gem.position, zustand) != zustand.config.bot_id:
            untake_gem(t_gem.position, zustand)

        elif gem_in_buffer(t_gem.position, zustand):
            new_gems_taken.append(t_gem)
    zustand.gems_taken = new_gems_taken


def untake_gem(pos: tuple, zustand: Zustand):
    for gem in zustand.gems_in_buffer:
        if pos == gem.position:
            if gem.taken:
                gem.taken = False
                msg = "1111" + "0" + put_zeros_infront_and_to_binary(gem.channel, 4)
                if zustand.bits_left < len(msg):
                    debug_print(
                        f"⚠️ Not enough bits left in buffer to write gem untaking message! Bits left: {zustand.bits_left}, needed: {len(msg)}",
                        zustand,
                    )
                    return
                zustand.bits_left -= len(msg)
                zustand.msgs_in_buffer.append(msg)
                zustand.msgs_written.append(msg)
            break


def put_buffer_together(zustand: Zustand):
    new_buffer = zustand.team_buffer[:12]
    for msg in zustand.msgs_in_buffer:
        new_buffer += msg

    bits_left = 256 - len(new_buffer)
    cut_map_update_to_right_length(zustand, bits_left)

    zustand.team_buffer = (
        new_buffer
        + zustand.map_update
        + "0" * (256 - len(zustand.map_update) - len(new_buffer))
    )


def cut_map_update_to_right_length(zustand: Zustand, bits_left):
    """cut to: len(map_update) <= bits_left"""
    if len(zustand.map_update) <= 18:
        zustand.map_update = ""
        return
    binary_buffer = zustand.map_update[2:]
    new_map_update = "10" + binary_buffer[:13]
    type_ = binary_buffer[0]
    binary_buffer = binary_buffer[1:]
    x, y = to_normal_koords(binary_buffer[:12])
    binary_buffer = binary_buffer[12:]
    bits_left -= 15 + 3  # 3 for Ending
    if bits_left <= 0:
        zustand.map_update = ""
        return
    while True:
        instruction = binary_buffer[:2]
        binary_buffer = binary_buffer[2:]
        if instruction == "11":
            instruction += binary_buffer[0]
            binary_buffer = binary_buffer[1:]

        if instruction == "111":
            new_map_update += "111"
            break
        elif instruction == "00":
            # /
            bits_left -= 2
            if bits_left <= 0:
                new_map_update += "111"
                break
            new_map_update += instruction
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "01":
            bits_left -= 2
            if bits_left <= 0:
                new_map_update += "111"
                break
            new_map_update += instruction
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "10":
            bits_left -= 2
            if bits_left <= 0:
                new_map_update += "111"
                break
            new_map_update += instruction
            if type_ == "0":
                y += 1
            else:
                x += 1
        elif instruction == "110":
            bits_left -= 3 + 12
            if bits_left <= 0:
                new_map_update += "111"
                break
            new_map_update += instruction
            # Shift
            x, y = to_normal_koords(binary_buffer[:12])
            new_map_update += binary_buffer[:12]
            binary_buffer = binary_buffer[12:]

    zustand.map_update = new_map_update
