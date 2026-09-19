import unittest
from types import SimpleNamespace
from tests.anyimage.common.support import load_common_modules

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
            properties=SimpleNamespace(
                inputs=SimpleNamespace(Mode=input_slot),
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
            properties=SimpleNamespace(
                inputs=SimpleNamespace(Thickness=input_slot),
            )
        )

        self.modules.object.set_modifier_input(runtime_modifier, "Thickness", 2.0)

        self.assertEqual(input_slot.value, 2.0)

        class DictionaryModifier(dict):
            properties = None

        dictionary_modifier = DictionaryModifier()
        self.modules.object.set_modifier_input(dictionary_modifier, "Mode", 1)
        self.assertEqual(dictionary_modifier["Mode"], 1)
