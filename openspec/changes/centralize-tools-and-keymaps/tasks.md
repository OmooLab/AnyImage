## 1. Centralize WorkspaceTool definitions

- [x] 1.1 Create `src/anyimage/tools.py` with the existing Frame, Mask, Rectify and Cutout WorkspaceTool declarations unchanged in behavior
- [x] 1.2 Add the ordered `TOOLS` list and shared register/unregister functions
- [x] 1.3 Remove WorkspaceTool definitions and exports from Operator modules, then update all imports to `tools.py`

## 2. Centralize keymap lifecycle

- [x] 2.1 Create `src/anyimage/keymaps.py` with `_items`, `_add()`, `register()` and `unregister()`
- [x] 2.2 Move the existing clipboard keymap definitions, platform modifier selection and support check into `keymaps.py`
- [x] 2.3 Remove clipboard-module keymap state and lifecycle exports without compatibility wrappers
- [x] 2.4 Update the extension entry point to call only the shared Tool and keymap lifecycle functions
- [x] 2.5 Declare shortcut and panel information as constants, make registration data-driven, and remove feature-specific support checks

## 3. Align tests and documentation

- [x] 3.1 Update existing Tool registration and settings tests for the centralized Tool module
- [x] 3.2 Update the existing clipboard shortcut test for the centralized keymap module without adding internal-framework tests
- [x] 3.3 Update affected internal architecture and Operator documentation without building documentation

## 4. Verify the change

- [x] 4.1 Confirm only `tools.py` defines WorkspaceTool and only `keymaps.py` owns extension keymap item lifecycle
- [x] 4.2 Run related registration, Tool, clipboard and packaging tests
- [x] 4.3 Run the full test suite and confirm normal completion
