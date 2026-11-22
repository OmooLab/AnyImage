import unittest
from types import SimpleNamespace
from tests.anyimage.common.support import load_common_modules


def node_group(name, identifier):
    socket = SimpleNamespace(item_type="SOCKET", in_out="INPUT", name=name, identifier=identifier)
    return SimpleNamespace(interface=SimpleNamespace(items_tree=[socket]))


class ModifierInputsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_common_modules()

    def test_runtime_modifier_enum_input_uses_string_identifier(self):
        enum_items = (
            SimpleNamespace(identifier="Balloon"),
            SimpleNamespace(identifier="Shell"),
        )
        value_property = SimpleNamespace(type="ENUM", enum_items=enum_items)
        input_slot = SimpleNamespace(
            value=None,
            bl_rna=SimpleNamespace(properties={"value": value_property}),
        )
        modifier = SimpleNamespace(
            node_group=node_group("Mode", "Socket_1"),
            properties=SimpleNamespace(
                inputs=SimpleNamespace(Socket_1=input_slot),
            )
        )

        self.modules.object.set_modifier_input(modifier, "Mode", 1)

        self.assertEqual(input_slot.value, "Shell")


    def test_modifier_inputs_support_rna_and_dictionary_values(self):
        value_property = SimpleNamespace(type="FLOAT")
        input_slot = SimpleNamespace(
            value=None,
            bl_rna=SimpleNamespace(properties={"value": value_property}),
        )
        runtime_modifier = SimpleNamespace(
            node_group=node_group("Thickness", "Socket_2"),
            properties=SimpleNamespace(
                inputs=SimpleNamespace(Socket_2=input_slot),
            )
        )

        self.modules.object.set_modifier_input(runtime_modifier, "Thickness", 2.0)

        self.assertEqual(input_slot.value, 2.0)
        self.assertEqual(self.modules.object.get_modifier_input(runtime_modifier, "Socket_2"), 2.0)

        class DictionaryModifier(dict):
            properties = None

        dictionary_modifier = DictionaryModifier()
        dictionary_modifier.node_group = node_group("Mode", "Socket_1")
        self.modules.object.set_modifier_input(dictionary_modifier, "Mode", 1)
        self.assertEqual(dictionary_modifier["Socket_1"], 1)
        self.assertEqual(self.modules.object.get_modifier_input(dictionary_modifier, "Socket_1"), 1)
        self.assertIsNone(self.modules.object.get_modifier_input(dictionary_modifier, "Missing"))
