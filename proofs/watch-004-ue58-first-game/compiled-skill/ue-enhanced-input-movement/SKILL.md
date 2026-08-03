---
name: ue-enhanced-input-movement
description: Build and verify a simple Unreal Engine 5.8 2D player movement slice using Enhanced Input. Use when creating IMC_Asteroids, IA_Move, BP_Player input wiring, or movement-orientation settings.
---

# UE Enhanced Input movement

Read `references/evidence-map.md` before changing a project. Treat the video
as a source of candidate procedure; verify names and defaults in the installed
UE version.

## Preconditions

- Unreal Engine 5.8 project exists and can be opened in an isolated workspace.
- A player Blueprint (`BP_Player`) and playable level exist.
- Enhanced Input is available; do not silently enable plugins or modify global
  settings without recording the change.

## Procedure

1. In `Content/Input`, create Input Mapping Context `IMC_Asteroids` and Input
   Action `IA_Move`.
2. Set `IA_Move` Value Type to `Axis2D` (`Vector2D`), not the default digital
   bool.
3. Add movement mappings in `IMC_Asteroids`: A and D use Swizzle Input Axis
   Values; A also uses Negate; S uses Negate. Preserve the demonstrated W/A/S/D
   intent, but inspect the modifier panels after each edit.
4. In `BP_Player` BeginPlay, get Player Controller, get Enhanced Input Local
   Player Subsystem, and call Add Mapping Context with `IMC_Asteroids`.
5. Add the EnhancedInputAction event for `IA_Move`; split its Action Value into
   X and Y. Route each axis to `Add Movement Input` using the project's intended
   world directions.
6. Compile, launch the level, and test W/A/S/D independently. Record the input
   value and player displacement; do not call this skill successful from a clean
   compile alone.
7. For character rotation, disable `Use Controller Rotation Yaw`, enable
   `Orient Rotation to Movement`, compile, and retest. Record the resulting
   orientation behavior.

## Validation gate

Pass only when the project compiles, each input produces the intended signed
axis value, the pawn moves in all four directions, and retained screenshots or
logs show the result. If a property or node is absent in the installed UE
version, stop and re-inspect the relevant source window instead of guessing.
