#!/usr/bin/env python

# Copyright (C) 2018 The University of Leeds.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Include a factory class to generate UR5 instances.

UR5 instances can be generated with different configuration. For example
the robot may have a ClearPath ridgeback, a two finger gripper etc where
in another setup the UR5 could not have the ridgeback, and could have
a three finger gripper instead.

This file define a class that let you create different robot configurations
on the fly.
"""

__author__ = "Rafael Papallas"
__authors__ = ["Rafael Papallas"]
__copyright__ = "Copyright (C) 2018, The University of Leeds"
__credits__ = ["Rafael Papallas", "Dr. Mehmet Dogar"]
__email__ = "Rafael: r.papallas@leeds.ac.uk  |  Mehmet: m.r.dogar@leeds.ac.uk"
__license__ = "GPLv3"
__maintainer__ = "Rafael Papallas"
__status__ = "Production"
__version__ = "0.0.1"

import rospy
from openravepy import Environment
from openravepy import RaveCreateIkSolver
from openravepy import RaveCreateModule
from openravepy import RaveInitialize
from openravepy import RaveLogInfo
from openravepy import RaveLogWarn
from ur5_robot import UR5_Robot


class UR5_Factory(object):
    """
    Class for generating UR5 robot configurations and environments.

    This class builds a UR5 robot by loading it from URDF files and
    also adds some other implementation details that are required. This
    class should be used to create UR5 instances in your OpenRAVE
    programs.
    """

    def __init__(self):
        """Initialise the UR5_Factory.

        Initialise the class by defining available grippers and
        viewers.
        """
        # TODO: Add support for robotiq_three_finger
        self._available_grippers = ["robotiq_two_finger"]

    def create_ur5_and_env(self, is_simulation=True,
                           has_ridgeback=True,
                           gripper_name="robotiq_two_finger",
                           has_force_torque_sensor=True,
                           env_path=None,
                           viewer_name="qtcoin",
                           urdf_path="package://ur5controller/ur5_description/urdf/",
                           srdf_path="package://ur5controller/ur5_description/srdf/"):
        """
        Create a UR5 and Environment instance.

        This method given some specifications as arguments, will build
        a UR5 robot instance accordingly.

        Args:
            is_simulation: Indicates whether the robot is in simulation
                           or not.
            has_ridgeback: Indicates whether the returned robot model
                           has a ClearPath Ridgeback moving base
                           integrated with it.
            gripper_name: The gripper name to be used in the robot model
                          among a list of available grippers.
            has_force_torque_sensor: Indicates whether the robot model
                                     will have a Robotiq Force Torque s
                                     ensor attached to it.
            env_path: The environment XML file to load from.
            viewer_name: The viewer name (e.g qtcoin, rviz etc) among
                         a list of available names.
            urdf_path: The path of the URDF files if you moved the URDFs
                       to another location, if you haven't, then leave this
                       to default.
            srdf_path: The path of the SRDF files if you moved the SRDFs
                       to another location, if you haven't, then leave this
                       to default.

        Returns:
            An openravepy.Environment and openravepy.Robot instances.

        Raises:
            ValueError: If gripper_name is invalid invalid.
        """
        if gripper_name not in self._available_grippers:
            raise ValueError("Gripper {} is not supported. The only " \
                             "available gripper names are: " \
                             "{}".format(gripper_name,
                                         ', '.join(self._available_grippers)))

        # TODO: Create URDFs that do not include the ridgeback.
        if not has_ridgeback:
            raise NotImplementedError("Robot configuration without ridgeback " \
                                      "is not yet available. Robot configuration " \
                                      "without the Clearpath Ridgeback is under " \
                                      "development at the moment (please check " \
                                      "that you also have the latest version " \
                                      "of this code).")

        RaveInitialize(True)
        self.env = self._create_environment(env_path)
        self.robot = self._load_ur5_from_urdf(gripper_name, has_ridgeback,
                                              has_force_torque_sensor, urdf_path,
                                              srdf_path)

        if not self._a_ros_topic_exist_with_the_name("joint_states"):
            is_simulation = True

        # Add class UR5_Robot to the robot.
        self.robot.__class__ = UR5_Robot
        self.robot.__init__(is_simulation)

        # Attach controllers
        if not is_simulation:
            self._attach_robot_controller()
            self._attach_gripper_controller(gripper_name)

        # Required for or_rviz to work with the robot's interactive marker.
        self._set_ik_solver()

        self._set_viewer(viewer_name)

        return self.env, self.robot

    def _set_ik_solver(self):
        ik_solver = RaveCreateIkSolver(self.env, self.robot.ikmodel.getikname())
        self.robot.manipulator.SetIkSolver(ik_solver)

    def _attach_gripper_controller(self, gripper_name):
        if gripper_name == "robotiq_two_finger":
            controller_name = "robotiqcontroller"

        if self._a_ros_topic_exist_with_the_name("CModelRobotInput"):
            self.robot.attach_controller(name=controller_name, dof_indices=[3])
            RaveLogInfo("robotiq_two_finger controller attached successfully.")
        else:
            RaveLogWarn("End-effector controller not attached, " \
                        "topics ('CModelRobotInput' or/and " \
                        "'CModelRobotOutput') are not available.")

    def _attach_robot_controller(self):
        # This is a defensive mechanism to avoid IsDone() method of the
        # end-effector controller block the program execution. For further
        # discussion, see this thread: https://stackoverflow.com/questions/49552755/openrave-controllerbase-is-blocking-at-the-isdone-method-and-never-returns/49552756#49552756
        if self._a_ros_topic_exist_with_the_name("joint_states"):
            self.robot.attach_controller(name="ur5controller",
                                         dof_indices=[2, 1, 0, 4, 5, 6])
            RaveLogInfo("UR5 controller attached successfully.")
        else:
            RaveLogWarn("UR5 Controller not attached to robot. Required " \
                        "topics not being published, rolling back to " \
                        "simulation.")

    def _a_ros_topic_exist_with_the_name(self, topic_name):
        # The ROS topic name always start with '/' character.
        if topic_name[0] != "/":
            topic_name = "/" + topic_name

        # List of all published ROS topics
        topics = rospy.get_published_topics()

        for topic in topics:
            if topic[0] == topic_name:
                return True

        return False

    def _get_file_name_from_specification(self, gripper_name, has_ridgeback,
                                          has_force_torque_sensor):
        """
        Return the correct URDF file given some configuration specification.

        Different robot configurations (with ridgeback and two-finger gripper
        or without ridgeback and with three-finger gripper) exists with
        different URDF and SRDF files. Hence this method given some
        specifications will return the appropriate URDF file from the
        package.

        Args:
            gripper_name: The gripper name to be loaded.
            has_ridgeback: Whether ClearPath Ridgeback will be loaded with
                the robot model.
            has_force_torque_sensor: Whether Robotiq force torque sensor
                will be loaded  with the robot model.

        Returns:
            A file name to a URDF/SRDF file matching the configuration
            specified by the arguments.
        """
        if gripper_name == "robotiq_two_finger" and has_ridgeback and has_force_torque_sensor:
            return "clearpath_ridgeback__ur5__robotiq_two_finger_gripper__robotiq_fts150"
        if gripper_name == "robotiq_two_finger" and has_ridgeback and not has_force_torque_sensor:
            return "clearpath_ridgeback__ur5__robotiq_two_finger_gripper"
        if gripper_name == "robotiq_three_finger" and has_ridgeback and has_force_torque_sensor:
            return "clearpath_ridgeback__ur5__robotiq_three_finger_gripper__robotiq_fts150"
        if gripper_name == "robotiq_three_finger" and has_ridgeback and not has_force_torque_sensor:
            return "clearpath_ridgeback__ur5__robotiq_three_finger_gripper"

    def _load_ur5_from_urdf(self, gripper_name, has_ridgeback,
                            has_force_torque_sensor, urdf_path, srdf_path):
        """
        Load a UR5 robot model from URDF to the environment.

        Given the appropriate configuration and valid path to URDF
        and SRDF files, will load UR5 in OpenRAVE environment and will
        return a robot instance back.

        Args:
            gripper_name: The gripper name to be loaded.
            has_ridgeback: Whether ClearPath Ridgeback will be loaded with
                the robot model.
            has_force_torque_sensor: Whether Robotiq force torque sensor
                will be loaded  with the robot model.
            urdf_path: The path of the URDF files.
            srdf_path: The path of the SRDF files.

        Returns:
            A UR5 openravepy.Robot instance.

        Raises:
            Exception: If or_urdf module cannot be loaded, or something
                went wrong while trying to load robot from a URDF file,
                or the robot couldn't be loaded from file.
        """

        file_name = self._get_file_name_from_specification(gripper_name,
                                                           has_ridgeback,
                                                           has_force_torque_sensor)

        urdf_path = urdf_path + "{}.urdf".format(file_name)
        srdf_path = srdf_path + "{}.srdf".format(file_name)

        urdf_module = RaveCreateModule(self.env, 'urdf')

        if urdf_module is None:
            raise Exception("Unable to load or_urdf module. Make sure you " \
                            "have or_urdf installed in your Catkin " \
                            "check: " \
                            "https://github.com/personalrobotics/or_urdf")

        ur5_name = urdf_module.SendCommand('LoadURI {} {}'.format(urdf_path,
                                                                  srdf_path))
        if ur5_name is None:
            raise Exception("Something went wrong while trying to load " \
                            "UR5 from file. Is the path correct?")

        robot = self.env.GetRobot(ur5_name)

        if robot is None:
            raise Exception("Unable to find robot with " \
                            "name '{}'.".format(ur5_name))

        return robot

    def _create_environment(self, env_path):
        """
        Create an Environment instance and load an XML environment to it.

        Will create an openravepy.Environment instance and will try to
        load an XML environment specification from file.

        Args:
            env_path: An XML file to load an environment.

        Returns:
            The openravepy.Environment instance.

        Raises:
            ValueError: If unable to load environment from file.
        """
        env = Environment()

        if env_path is not None:
            if not env.Load(env_path):
                raise ValueError("Unable to load environment " \
                                 "file: '{}'".format(env_path))

        return env

    def _set_viewer(self, viewer_name):
        """
        Set the viewer using the user-specified viewer_name.

        Args:
            viewer_name: The name of viewer to be set.

        Raises:
            Exception: If there was a problem setting the viewer.
        """
        self.env.SetViewer(viewer_name)
        if self.env.GetViewer() is None:
            raise Exception("There was something wrong when loading " \
                            "the {} viewer.".format(viewer_name))
