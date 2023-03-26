from typing import Dict, List, Tuple
from pymodbus.exceptions import ModbusException

from parsers.network import InputArcTypes, Transition
from parsers.device import InputEvent, OutputEvent
from modbus_client import ModbusClient
from special_tokens import strip_name, COMMENT


def check_transition(rising: bool, signal_values: Tuple[bool, bool]):
    """
    A convenience function just to check if two values of a signal
    represent a rising or falling transition.
    """
    previous, next = signal_values
    return previous != next == rising


class Controller:
    def __init__(
        self,
        address: Tuple[str, int],
        transitions: List[Transition],
        places: Dict[str, int],
        inputs: Dict[str, InputEvent],
        outputs: Dict[str, OutputEvent],
    ):
        self.client = ModbusClient(address)
        self.transitions = transitions
        self.places = places
        self.inputs = inputs
        self.outputs = outputs

        # Get all the addresses. These addresses appear more than once in the .net file
        # so use a set to avoid repeats
        self.addresses = set(
            [i[0] for value in self.inputs.values() for i in value.triggers]
        )

        # Intantiate the read values to false. This is needed because we use rising and falling
        # edges. While it would be possible to use the direct values, this misses the point because
        # tina is supposed to be for *event* oriented programming
        # This using a tuple because it stores the current and previous value
        self.read_values = {
            address: (False, False) for address in self.addresses
        }

    def read(self, event: str) -> bool:
        """
        Read the value of a signal from the bus. This isn't very useful in practice,
        I *think* because this would read an address multiple times if it appeared more than once
        It's probably faster to use the current system of reading all the values and
        acting based on that
        """
        result = False
        for trigger in self.inputs[event].triggers:
            try:
                readval = self.client.read_discrete_inputs(trigger[0])
                result = result or readval.bits[0]
            except ModbusException as e:
                raise ConnectionResetError("Can't read discrete input") from e

        return result

    def write(self, event: str):
        """
        Write an event to the bus to trigger eg. a belt
        """
        print(f"  e: {event}")
        for action in self.outputs[event].actions:
            try:
                self.client.write_coil(*action)
            except ModbusException as e:
                raise ConnectionResetError("Can't write to coils") from e

    def read_all(self):
        """
        Read the values from all available addresses and update [read_values]
        """
        for address in self.addresses:
            try:
                input_vals = self.client.read_discrete_inputs(address)
                self.read_values[address] = (
                    self.read_values[address][1],
                    input_vals.bits[0],
                )
            except ModbusException as e:
                raise ConnectionResetError("Can't read discrete inputs") from e

    def loop(self):
        """
        The main loop. I ran this every 10ms
        """

        # Update the read values
        self.read_all()

        # Iterate through all the transitions in a network
        for transition in self.transitions:
            # Check if the FlexFact requirements are met (ie. if a sensor has just turn on or off)
            # Adding ; to the start of a name means it is ignored and the transition is allowed
            if not transition.name.startswith(COMMENT):
                name = strip_name(transition.name)
                if name in self.inputs:
                    # There are technically multiple triggers defined
                    # This probably should be modified to work too, instead of using [0],
                    # but in my use it was never needed. I can't actually think when this
                    # would be used

                    # Should it be rising or falling to transition
                    rising = self.inputs[name].triggers[0][1]
                    address = self.inputs[name].triggers[0][0]

                    # Check if the signal is rising or falling, or vice-versa
                    did_transition = check_transition(
                        rising, self.read_values[address]
                    )
                else:
                    did_transition = True
            else:
                did_transition = True

            # If all requirements are met
            if transition.is_enabled(self.places) and did_transition:
                print(f"  t: {transition.name}")

                # Move the tokens around
                # This is a basic implementation of a Petri net runner
                for input_arc in transition.input_arcs:
                    place = input_arc.place
                    weight = input_arc.weight
                    _type = input_arc.type

                    if _type == InputArcTypes.REGULAR:
                        self.places[place] -= weight
                for output_arc in transition.output_arcs:
                    place = output_arc.place
                    weight = output_arc.weight

                    self.places[place] += weight

                # Issue the commands via Modbus. Note that ; is also used to
                # separate between command in the name, so you can use less places
                # This hasn't been tested much
                if strip_name(transition.name) in self.outputs:
                    values = transition.name.split(COMMENT)
                    if values[0]:
                        for v in values:
                            self.write(strip_name(v))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.client.close()
