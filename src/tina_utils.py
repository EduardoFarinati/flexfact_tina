from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union
from pathlib import Path


@dataclass
class Transition:
    """
    Representation of a tina arrow or equivalent
    Includes the conditions required to move
    """

    name: str
    reqs: List = field(default_factory=list)
    outs: List = field(default_factory=list)


def parse_network(
    filepath: Union[Path, str]
) -> Tuple[List[Transition], Dict[str, int]]:
    """Parse the text file generated by tina export."""

    transitions = []
    places = {}

    with open(filepath, "r") as file:
        for line in file:
            elements = (
                line.strip()
                .replace("\n", "")
                .replace("\r", "")
                .replace("{", "")
                .replace("}", "")
                .split()
            )
            if len(elements) == 0:
                continue
            elif elements[0] == "tr":
                transition = Transition(elements[1])
                arrow_index = elements.index("->")
                for element in elements[3:arrow_index]:
                    if "?" in element:
                        parts = element.split("?")
                        if int(parts[1]) > 0:
                            transition.reqs.append(
                                (parts[0], int(parts[1]), True)
                            )
                        else:
                            transition.reqs.append(
                                (parts[0], abs(int(parts[1])), False)
                            )
                    else:
                        parts = element.split("*")
                        if len(parts) == 1:
                            transition.reqs.append((parts[0], 1, None))
                        else:
                            transition.reqs.append(
                                (parts[0], int(parts[1]), None)
                            )
                if arrow_index + 1 != len(elements):
                    for element in elements[arrow_index + 1 :]:
                        parts = element.split("*")
                        places[parts[0]] = 0
                        if len(parts) == 1:
                            transition.outs.append((parts[0], 1))
                        else:
                            transition.outs.append((parts[0], int(parts[1])))

                transitions.append(transition)

            elif elements[0] == "pl":
                places[elements[1]] = int(
                    elements[2].replace("(", "").replace(")", "")
                )

    return transitions, places
