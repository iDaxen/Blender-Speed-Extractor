import bpy
import math
import csv
import os
import tempfile

bl_info = {
    "name": "Speed Extractor",
    "blender": (3, 4, 0),
    "category": "Object",
    "description": "Measures the horizontal speed of an object and allows to use the data in Shader Editor, Geo Nodes, and export as csv file.",
    "author": "Daxen",
}

class SpeedDataProcessorProperties(bpy.types.PropertyGroup):
    text_block_name: bpy.props.StringProperty(
        name="Text Block Name",
        description="Name of the text block containing speed data",
        default="speed_data"
    )
    apply_averaging: bpy.props.BoolProperty(
        name="Apply Averaging",
        description="Smooth speed data using a simple moving average",
        default=False
    )
    averaging_window: bpy.props.IntProperty(
        name="Averaging Window",
        description="Number of frames to average over",
        default=5,
        min=1
    )
    use_interval: bpy.props.BoolProperty(
        name="Use Interval",
        description="Measure speed at intervals",
        default=False
    )
    interval: bpy.props.IntProperty(
        name="Interval",
        description="Interval for measuring speed",
        default=1,
        min=1
    )
    text_before: bpy.props.StringProperty(
        name="Text Before",
        description="Text to display before the speed value",
        default=""
    )
    text_after: bpy.props.StringProperty(
        name="Text After",
        description="Text to display after the speed value",
        default=""
    )

class OBJECT_OT_GetSpeed(bpy.types.Operator):
    bl_idname = "object.get_speed"
    bl_label = "Get Speed"
    bl_description = "Select the object you want to get the Speed from"

    def execute(self, context):
        props = context.scene.speed_data_processor
        obj = context.object

        if obj is None:
            self.report({'ERROR'}, "No object selected")
            return {'CANCELLED'}

        # Get frames from the current scene
        scene = context.scene
        start_frame = scene.frame_start
        end_frame = scene.frame_end
        interval = props.interval if props.use_interval else 1

        # Create or clear the text block
        if props.text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[props.text_block_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name=props.text_block_name)

        # Measure horizontal speed for each frame and record in text block
        prev_location = None
        speed_data = []
        for frame in range(start_frame, end_frame + 1, interval):
            scene.frame_set(frame)
            location = obj.location.copy()

            if prev_location is not None:
                dx = location.x - prev_location.x
                dy = location.y - prev_location.y
                horizontal_distance = math.sqrt(dx**2 + dy**2)

                # Convert frame difference to time in seconds
                time = interval / scene.render.fps
                speed = (horizontal_distance / time) * 100  # Scale speed
                speed_data.append((frame - interval, frame, round(speed)))

            prev_location = location

        if props.apply_averaging:
            averaged_data = []
            for i in range(len(speed_data)):
                window_start = max(0, i - props.averaging_window // 2)
                window_end = min(len(speed_data), i + props.averaging_window // 2 + 1)
                window = speed_data[window_start:window_end]
                avg_speed = sum([d[2] for d in window]) / len(window)
                averaged_data.append((speed_data[i][0], speed_data[i][1], round(avg_speed)))
            speed_data = averaged_data

        for frame_start, frame_end, speed in speed_data:
            text_block.write(f"{frame_start},{frame_end},{speed}\n")

        self.report({'INFO'}, "Speed data recorded")
        return {'FINISHED'}

class OBJECT_OT_TransferToShaderEditor(bpy.types.Operator):
    bl_idname = "object.transfer_to_shader_editor"
    bl_label = "Transfer to Shader Editor"
    bl_description = "Select the object and active material you want to create the Value Node for"

    def execute(self, context):
        props = context.scene.speed_data_processor
        text_block_name = props.text_block_name

        if text_block_name not in bpy.data.texts:
            self.report({'ERROR'}, f"No text block named '{text_block_name}' found")
            return {'CANCELLED'}

        speed_data_text = bpy.data.texts[text_block_name].as_string()
        frame_data = [line.split(',') for line in speed_data_text.strip().split('\n')]

        obj = context.object
        material = obj.active_material

        if not material:
            self.report({'ERROR'}, "Active object has no material")
            return {'CANCELLED'}

        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        frame_numbers = [int(data[1]) for data in frame_data]
        speeds = [float(data[2]) for data in frame_data]

        value_node = nodes.new(type='ShaderNodeValue')
        value_node.name = "Speed Value"
        value_node.label = "Speed Value"
        value_node.location = (0, 0)

        # Ensure the material has animation data
        if material.node_tree.animation_data is None:
            material.node_tree.animation_data_create()

        action = material.node_tree.animation_data.action
        if not action:
            action = bpy.data.actions.new(name="SpeedAction")
            material.node_tree.animation_data.action = action

        fcurve = action.fcurves.new(data_path=f'nodes["{value_node.name}"].outputs[0].default_value')

        for frame, speed in zip(frame_numbers, speeds):
            keyframe = fcurve.keyframe_points.insert(frame, speed)
            keyframe.interpolation = 'CONSTANT'

        # Print highest and lowest speeds
        max_speed = max(speeds)
        min_speed = min(speeds)
        print(f"Highest Speed: {max_speed}")
        print(f"Lowest Speed: {min_speed}")

        self.report({'INFO'}, "Speed data transferred to Shader Editor")
        return {'FINISHED'}

class OBJECT_OT_TransferToGeoNodes(bpy.types.Operator):
    bl_idname = "object.transfer_to_geonodes"
    bl_label = "Transfer to GeoNodes"
    bl_description = "Select the Geo-Node set up you want the data to be transferred to"

    def execute(self, context):
        props = context.scene.speed_data_processor
        text_block_name = props.text_block_name

        if text_block_name not in bpy.data.texts:
            self.report({'ERROR'}, f"No text block named '{text_block_name}' found")
            return {'CANCELLED'}

        speed_data_text = bpy.data.texts[text_block_name].as_string()
        frame_data = [line.split(',') for line in speed_data_text.strip().split('\n')]

        obj = context.object

        modifier = None
        for mod in obj.modifiers:
            if mod.type == 'NODES':
                modifier = mod
                break

        if not modifier:
            self.report({'ERROR'}, "Active object has no Geometry Nodes modifier")
            return {'CANCELLED'}

        node_group = modifier.node_group
        nodes = node_group.nodes
        links = node_group.links

        frame_numbers = [int(data[1]) for data in frame_data]
        speeds = [float(data[2]) for data in frame_data]

        value_node = nodes.new(type='ShaderNodeValue')
        value_node.name = "Speed Value"
        value_node.label = "Speed Value"
        value_node.location = (0, 0)

        # Ensure the node group has animation data
        if node_group.animation_data is None:
            node_group.animation_data_create()

        action = node_group.animation_data.action
        if not action:
            action = bpy.data.actions.new(name="GeoNodesSpeedAction")
            node_group.animation_data.action = action

        fcurve = action.fcurves.new(data_path=f'nodes["{value_node.name}"].outputs[0].default_value')

        for frame, speed in zip(frame_numbers, speeds):
            keyframe = fcurve.keyframe_points.insert(frame, speed)
            keyframe.interpolation = 'CONSTANT'

        # Print highest and lowest speeds
        max_speed = max(speeds)
        min_speed = min(speeds)
        print(f"Highest Speed: {max_speed}")
        print(f"Lowest Speed: {min_speed}")

        self.report({'INFO'}, "Speed data transferred to Geometry Nodes")
        return {'FINISHED'}

class OBJECT_OT_DisplaySpeed(bpy.types.Operator):
    bl_idname = "object.display_speed"
    bl_label = "Display Speed as Text"
    bl_description = "Display speed data as text in the viewport"

    def execute(self, context):
        props = context.scene.speed_data_processor

        # Check if the text object already exists
        if "SpeedText" not in bpy.data.objects:
            # Create a new text object
            bpy.ops.object.text_add(location=(0, 0, 0))
            text_object = bpy.context.object
            text_object.name = "SpeedText"
            text_object.data.body = "0"
            text_object.data.size = 1  # Adjust the text size if necessary

            # Set alignment to center
            text_object.data.align_x = 'CENTER'
            
            # Update origin to the center of the text
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='BOUNDS')
        else:
            text_object = bpy.data.objects["SpeedText"]

        def parse_speed_data(text_block_name):
            speed_data = {}
            if text_block_name in bpy.data.texts:
                speed_data_text = bpy.data.texts[text_block_name].as_string()
                for line in speed_data_text.strip().split('\n'):
                    frame_start, frame_end, speed = map(float, line.split(','))
                    frame_start = int(frame_start)
                    frame_end = int(frame_end)
                    for frame in range(frame_start, frame_end + 1):
                        speed_data[frame] = round(speed)
            else:
                print(f"Text block '{text_block_name}' not found.")
            return speed_data

        text_block_name = context.scene.speed_data_processor.text_block_name
        speed_data = parse_speed_data(text_block_name)

        def update_text(scene):
            current_frame = scene.frame_current
            speed = speed_data.get(current_frame, 0)  # Default to 0 if no data for the current frame
            
            text_object = bpy.data.objects.get("SpeedText")
            if text_object is not None:
                text_before = props.text_before
                text_after = props.text_after
                text_body = f"{text_before}{speed}{text_after}" if text_before or text_after else f"{speed}"
                text_object.data.body = text_body  # Update the text with the current speed
                text_object.keyframe_insert(data_path="data.body", frame=current_frame)  # Add keyframe

        bpy.app.handlers.frame_change_post.clear()
        bpy.app.handlers.frame_change_post.append(update_text)

        self.report({'INFO'}, "Text object created and updated with speed data")
        return {'FINISHED'}

class SpeedDataProcessorPanel(bpy.types.Panel):
    bl_label = "Speed Data Processor"
    bl_idname = "OBJECT_PT_speed_data_processor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Speed Processor"

    def draw(self, context):
        layout = self.layout
        props = context.scene.speed_data_processor

        layout.prop(props, "text_block_name")
        layout.prop(props, "apply_averaging")
        if props.apply_averaging:
            layout.prop(props, "averaging_window")
        layout.prop(props, "use_interval")
        if props.use_interval:
            layout.prop(props, "interval")
        layout.prop(props, "text_before")
        layout.prop(props, "text_after")

        layout.operator("object.get_speed", text="Get Speed")
        layout.operator("object.transfer_to_shader_editor", text="Transfer to Shader Editor")
        layout.operator("object.transfer_to_geonodes", text="Transfer to GeoNodes")
        layout.operator("object.display_speed", text="Display Speed as Text")

classes = [
    SpeedDataProcessorProperties,
    OBJECT_OT_GetSpeed,
    OBJECT_OT_TransferToShaderEditor,
    OBJECT_OT_TransferToGeoNodes,
    OBJECT_OT_DisplaySpeed,
    SpeedDataProcessorPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.speed_data_processor = bpy.props.PointerProperty(type=SpeedDataProcessorProperties)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.speed_data_processor

if __name__ == "__main__":
    register()
