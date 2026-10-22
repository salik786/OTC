# Pepper model — sources and licenses

- **Meshes and textures** (`Pepper.fbx` geometry, `Textures/juliette_*`): Aldebaran (SoftBank
  Robotics) Pepper model, from the Pepper SDK (`alrobotmodel/meshes/juliette`). Licensed by
  Aldebaran under **Creative Commons Attribution-NonCommercial-NoDerivatives 4.0** — non-commercial
  research use only, with attribution. Converted from Ogre3D format to FBX without modifying the
  geometry. Do not use commercially, and check with the project supervisor before publishing the
  repository or the model publicly.
- **Kinematics** (joint positions/axes used to assemble the parts): `pepper_description` URDF from
  [ros-naoqi/pepper_robot](https://github.com/ros-naoqi/pepper_robot), Apache 2.0.
- **Pose**: NAOqi `StandInit` posture from the Pepper SDK.

Regenerate with `Tools/pepper/build_pepper.py` (see the docstring for the Blender command).

Suggested credit in publications: "Pepper 3D model © Aldebaran / SoftBank Robotics, used under
CC BY-NC-ND 4.0."
