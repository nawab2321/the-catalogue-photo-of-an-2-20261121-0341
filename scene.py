"""Build and path-trace the Nimbus No. 2 studio setup with Blender 4.5."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True, type=Path)
parser.add_argument("--samples", default=144, type=int)
parser.add_argument("--size", default=1024, type=int)
options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def linear(rgb):
    return tuple(
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in rgb
    )


def finish(name, rgb, roughness, metallic=0.0, grain=None, coat=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*linear(rgb), 1)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = material.diffuse_color
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Coat Weight"].default_value = coat
    shader.inputs["Coat Roughness"].default_value = 0.31
    if grain:
        stretch, scale, strength, depth = grain
        coordinates = nodes.new("ShaderNodeTexCoord")
        direction = nodes.new("ShaderNodeVectorMath")
        direction.operation = "MULTIPLY"
        direction.inputs[1].default_value = stretch
        links.new(coordinates.outputs["Object"], direction.inputs[0])
        texture = nodes.new("ShaderNodeTexNoise")
        texture.inputs["Scale"].default_value = scale
        texture.inputs["Detail"].default_value = 2.2
        links.new(direction.outputs[0], texture.inputs["Vector"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = strength
        bump.inputs["Distance"].default_value = depth
        links.new(texture.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


enamel = finish("Vermilion powder-coated casting", (.83, .197, .081), .42, .13,
                ((1, 1, 1), 70, .26, .014), .18)
enamel_dark = finish("Vermilion recessed face", (.74, .156, .071), .43, .12,
                     ((1, 1, 1), 72, .22, .013), .16)
graphite = finish("Graphite bead-blasted aluminum", (.238, .263, .276), .38, .70,
                  ((1, 1, 1), 115, .13, .01), .10)
rubber = finish("Fine-grain charcoal elastomer", (.112, .127, .139), .48, .0,
                ((1, 1, 1), 102, .22, .013))
steel = finish("Satin turned stainless steel", (.70, .735, .75), .245, .94,
               ((1, 1, 12), 45, .15, .008))
edge_steel = finish("Polished cut edges", (.81, .835, .85), .145, .98)
black = finish("Recesses and oxide steel", (.096, .109, .114), .39, .55)
spring_steel = finish("Oiled spring steel", (.49, .521, .545), .25, .94)
mark = finish("Ivory pad print", (.938, .897, .79), .55)
metal_print = finish("Etched silver", (.63, .675, .66), .53, .25)
floor_mat = finish("Warm gray seamless paper", (.75, .714, .66), .79,
                   grain=((1, 1, 1), 120, .07, .007))
glass = finish("Clear molded copolyester", (.98, .994, 1), .12)
glass_shader = glass.node_tree.nodes.get("Principled BSDF")
glass_shader.inputs["Transmission Weight"].default_value = 1.0
glass_shader.inputs["IOR"].default_value = 1.49


def bevel_mesh(obj, width, segments=4):
    bevel = obj.modifiers.new("Machined edge radii", "BEVEL")
    bevel.width = width
    bevel.segments = segments
    bevel.harden_normals = True
    normal = obj.modifiers.new("Face-weighted normals", "WEIGHTED_NORMAL")
    normal.keep_sharp = True


def mesh(name, vertices, faces, materials):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    for material in materials:
        data.materials.append(material)
    return obj


def box(name, position, dimensions, material, bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        bevel_mesh(obj, bevel)
    return obj


def easing_polygon(points):
    """Round extruded profiles in their own plane before adding the edge radius."""
    outline = []
    for index, (x, z, setback) in enumerate(points):
        previous = Vector(points[index - 1][:2])
        corner = Vector((x, z))
        following = Vector(points[(index + 1) % len(points)][:2])
        incoming = previous - corner
        outgoing = following - corner
        start = corner + incoming.normalized() * min(setback, incoming.length * .46)
        end = corner + outgoing.normalized() * min(setback, outgoing.length * .46)
        for segment in range(7):
            t = segment / 6
            outline.append((1 - t) ** 2 * start + 2 * (1 - t) * t * corner + t ** 2 * end)
    return outline


def profile(name, points, y_front, y_back, material, radius):
    outline = easing_polygon(points)
    count = len(outline)
    vertices = [(x, y, z) for y in (y_front, y_back) for x, z in outline]
    faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((next_index, index, index + count, next_index + count))
    obj = mesh(name, vertices, faces, [material])
    bevel_mesh(obj, radius, 5)
    return obj


def turned(name, origin, profile_points, materials, axis=(0, 0, 1), steps=96):
    """Revolve a closed section with optional material changes at each shoulder."""
    vertices = []
    rings = []
    for radius, height, _ in profile_points:
        ring = []
        for index in range(steps if radius > 0 else 1):
            angle = index / steps * math.tau
            ring.append(len(vertices))
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), height))
        rings.append(ring)
    faces = []
    face_materials = []
    for index, ring in enumerate(rings):
        following = rings[(index + 1) % len(rings)]
        if len(ring) == len(following) == 1:
            continue
        for j in range(steps):
            k = (j + 1) % steps
            if len(ring) == 1:
                face = (ring[0], following[k], following[j])
            elif len(following) == 1:
                face = (ring[j], ring[k], following[0])
            else:
                face = (ring[j], ring[k], following[k], following[j])
            faces.append(face)
            face_materials.append(profile_points[index][2])
    obj = mesh(name, vertices, faces, materials)
    obj.location = origin
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector(axis).to_track_quat("Z", "Y")
    for face, index in zip(obj.data.polygons, face_materials):
        face.material_index = index
        face.use_smooth = True
    return obj


def cylinder(name, center, radius, depth, material, axis=(0, 0, 1), bevel=.009, steps=64):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=steps, radius=radius, depth=depth, location=center
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector(axis).to_track_quat("Z", "Y")
    obj.data.materials.append(material)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    if bevel:
        bevel_mesh(obj, bevel, 3)
    return obj


def screw(name, position, radius=.062, axis=(0, -1, 0)):
    turned(name, position, [
        (0, 0, 1), (radius * .86, 0, 0), (radius, .009, 0),
        (radius, .022, 0), (radius * .80, .032, 1),
        (radius * .45, .032, 0), (radius * .37, .022, 1), (0, .022, 1)
    ], [steel, edge_steel], axis, 48)
    socket = Vector(position) + Vector(axis) * .023
    cylinder("Recessed hex socket", socket, radius * .35, .003, black, axis, 0, 6)


def text_on_face(name, body, position, size, material, spacing=1.0):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = body
    curve.size = size
    curve.space_character = spacing
    obj = bpy.data.objects.new(name, curve)
    obj.location = position
    obj.rotation_euler = (math.pi / 2, 0, 0)
    scene.collection.objects.link(obj)
    curve.materials.append(material)
    return obj


# Chassis, including an open throat and a cantilevered die seat.
head_lift = .26


def raised(points):
    """Keep the casting feet fixed while increasing throat clearance."""
    return [(x, z + head_lift * min(1, max(0, (z - .55) / .96)), edge)
            for x, z, edge in points]


box("Cast graphite sole", (-.65, .035, .157), (3.02, 1.44, .208), graphite, .091)
box("Recessed rubber sole", (-.65, .035, .068), (2.86, 1.30, .105), rubber, .047)
box("Casting to sole seam", (-1.365, .105, .275), (1.51, 1.03, .07), black, .031)
box("Vermilion foot", (-1.36, .107, .332), (1.50, 1.00, .16), enamel, .064)
for x in (-1.91, -.85):
    for y in (-.31, .51):
        screw("Sole mounting screw", (x, y, .397), .061, (0, 0, 1))

frame = [
    (-2.085, .36, .15), (-.94, .36, .17), (-.90, .52, .10),
    (-1.27, .64, .16), (-1.38, .82, .16), (-1.38, 1.48, .28),
    (-1.28, 1.75, .23), (-1.02, 1.94, .23), (.565, 1.94, .16),
    (.720, 2.085, .095), (.720, 2.385, .09), (.585, 2.49, .125),
    (-1.68, 2.49, .22), (-1.995, 2.26, .26), (-2.085, 1.71, .25),
]
profile("One-piece cast C frame", raised(frame), -.328, .505, enamel, .052)

cover = [
    (-1.982, .55, .13), (-1.53, .55, .07), (-1.47, .70, .10),
    (-1.51, 1.57, .16), (-1.39, 1.81, .13), (-1.10, 2.055, .16),
    (.495, 2.055, .13), (.56, 2.14, .07), (.56, 2.32, .06),
    (.45, 2.39, .09), (-1.64, 2.39, .18), (-1.88, 2.21, .14),
    (-1.982, 1.69, .18),
]
profile("Fitted casting cover seam", raised(cover), -.341, -.310, black, .011)
profile("Fitted vermilion service cover", raised(cover), -.362, -.339, enamel_dark, .009)
for x, z, _ in raised([(-1.79, .73, 0), (-1.81, 1.65, 0),
                        (-1.59, 2.245, 0), (.427, 2.226, 0)]):
    screw("Service cover screw", (x, -.364, z), .047)

box("Recessed maker plate", (-.463, -.373, 2.229 + head_lift),
    (1.002, .026, .247), graphite, .026)
text_on_face("Maker mark", "NIMBUS", (-.880, -.3875, 2.209 + head_lift), .151, mark, 1.27)
text_on_face("Model engraving", "NO. 2", (-.874, -.388, 2.124 + head_lift), .073, metal_print, 1.19)
text_on_face("Calibration engraving", "Ø 18", (-.074, -.388, 2.124 + head_lift), .061, metal_print)

box("Cantilevered lower die carrier", (-.715, -.102, .855 + head_lift),
    (1.55, .55, .162), graphite, .073)
box("Recessed die carrier front lip", (-.753, -.375, .841 + head_lift),
    (1.35, .030, .09), black, .022)
for x in (-1.13, -.61):
    screw("Anvil carrier screw", (x, -.389, .847 + head_lift), .043)

punch_x, punch_y = .38, -.185
turned("Hollow receiving die", (punch_x, punch_y, .819 + head_lift), [
    (.286, 0, 0), (.407, 0, 1), (.431, .018, 0), (.440, .037, 0),
    (.440, .100, 0), (.434, .112, 1), (.415, .125, 0),
    (.329, .125, 1), (.302, .108, 0), (.286, .076, 0)
], [steel, edge_steel])
turned("Knurled lower die register", (punch_x, punch_y, .779 + head_lift), [
    (.31, 0, 0), (.381, 0, 0), (.397, .012, 0),
    (.397, .038, 1), (.381, .048, 0), (.31, .048, 0)
], [graphite, steel])
for index in range(42):
    angle = math.tau * index / 42
    tick = box(
        "Die register knurl", (punch_x + .397 * math.cos(angle),
        punch_y + .397 * math.sin(angle), .804 + head_lift), (.011, .009, .025), black, .003
    )
    tick.rotation_euler.z = angle

turned("Press nose bushing", (punch_x, punch_y, 1.757 + head_lift), [
    (.183, 0, 0), (.334, 0, 1), (.359, .019, 0), (.371, .049, 0),
    (.371, .237, 0), (.355, .256, 0), (.185, .256, 0),
], [graphite, steel])
turned("Ground ram and replaceable cutting sleeve", (punch_x, punch_y, 1.202 + head_lift), [
    (.268, 0, 1), (.309, .025, 1), (.340, .062, 0), (.344, .114, 0),
    (.344, .235, 0), (.331, .262, 1), (.297, .283, 0), (.212, .289, 0),
    (.194, .313, 0), (.187, .556, 0), (.187, .653, 0), (0, .653, 0),
    (0, .140, 0), (.259, .140, 1)
], [steel, edge_steel])
for z in (1.475, 1.541, 1.690):
    turned("Circular machining witness line", (punch_x, punch_y, z + head_lift), [
        (.185, 0, 0), (.193, 0, 0), (.193, .010, 0), (.185, .010, 0)
    ], [black], steps=64)

spring = bpy.data.curves.new("Ram return spring", "CURVE")
spring.dimensions = "3D"
spring.bevel_depth = .0215
spring.bevel_resolution = 5
helix = spring.splines.new("POLY")
helix.points.add(239)
for index, point in enumerate(helix.points):
    t = index / 239
    phase = t * 4.25 * math.tau
    # The end turns are wound tighter to sit flat on their shoulders.
    rise = .21 * (.85 * t + .15 * (1 - math.cos(math.pi * t)) / 2)
    point.co = (punch_x + .222 * math.cos(phase), punch_y + .222 * math.sin(phase),
                1.521 + head_lift + rise, 1)
return_spring = bpy.data.objects.new("Exposed ram return spring", spring)
scene.collection.objects.link(return_spring)
spring.materials.append(spring_steel)


# Lever cheeks, bushed pivot, and rubber grip.
pivot = Vector((-1.56, .057, 2.48 + head_lift))
lever_axis = Vector((1, 0, .255)).normalized()
lever_points = [
    (-1.795, 2.455, .14), (-1.67, 2.655, .12), (-1.43, 2.677, .12),
    (1.11, 3.282, .065), (1.25, 3.272, .048), (1.25, 3.146, .047),
    (1.09, 3.088, .10), (-1.42, 2.435, .14), (-1.68, 2.352, .12),
]
for front in (-.305, .290):
    profile("Steel lever fork", raised(lever_points), front, front + .12, graphite, .033)
cylinder("Ground pivot axle", pivot, .134, .918, steel, (0, -1, 0), .02)
for y, direction in ((-.399, -1), (.514, 1)):
    cylinder("Pivot shoulder washer", (-1.56, y, pivot.z), .163, .057,
             edge_steel, (0, direction, 0), .012)
    screw("Pivot retaining cap", (-1.56, y + direction * .025, pivot.z),
          .108, (0, direction, 0))
link = box("Ram input link", (.39, .038, 2.650 + head_lift), (.245, .42, .424), steel, .041)
link.rotation_euler.y = .13
cylinder("Link pin", (.385, .043, 2.850 + head_lift), .060, .624, steel, (0, 1, 0), .008)
for y, direction in ((-.276, -1), (.361, 1)):
    cylinder("Link snap ring", (.385, y, 2.850 + head_lift), .077, .025, black, (0, direction, 0))

grip_origin = Vector((.868, .043, 3.151 + head_lift))
turned("Grip aluminum ferrule", grip_origin, [
    (0, -.015, 0), (.131, -.015, 1), (.147, .008, 0),
    (.149, .128, 0), (.163, .152, 1), (.162, .189, 0), (0, .189, 0)
], [steel, edge_steel], lever_axis)
grip_section = [(0, .145, 0), (.125, .145, 0), (.169, .164, 0), (.183, .206, 0)]
for index in range(7):
    start = .259 + index * .071
    grip_section.extend([(.183, start, 0), (.174, start + .009, 0),
                         (.174, start + .017, 0), (.183, start + .026, 0)])
grip_section.extend([(.183, .746, 0), (.174, .790, 0), (.155, .819, 0),
                     (.121, .836, 0), (0, .836, 0)])
turned("Fluted lever grip", grip_origin, grip_section, [rubber], lever_axis)

# The catcher is the single removable accessory. Its rim sits below the ejector.
cup_x, cup_y = .45, -.309
turned("Catcher carrier groove", (cup_x, cup_y, .226), [
    (.243, 0, 0), (.393, 0, 1), (.404, .014, 0),
    (.404, .039, 0), (.395, .052, 1), (.290, .052, 1), (.243, .037, 0)
], [black, graphite])
turned("Transparent catch cup", (cup_x, cup_y, .263), [
    (0, 0, 0), (.276, 0, 0), (.321, .014, 0), (.343, .040, 0),
    (.366, .262, 0), (.367, .284, 0), (.361, .303, 0), (.344, .309, 0),
    (.329, .301, 0), (.327, .277, 0), (.308, .063, 0), (.275, .043, 0),
    (0, .043, 0)
], [glass])
turned("Integral catcher foot", (cup_x, cup_y, .282), [
    (.291, 0, 0), (.320, 0, 0), (.334, .009, 0), (.341, .017, 1),
    (.343, .029, 0), (.335, .035, 0), (.323, .030, 0), (.291, .015, 0)
], [steel, edge_steel])
box("Clear molded catcher pull tab", (cup_x, cup_y - .358, .482),
    (.225, .155, .052), glass, .025)


# The workpiece is participating media. A soft union of lobe fields gives the
# cumulus its form, then the two cylindrical bores cut directly into density.
origin = bpy.data.objects.new("Volume coordinate origin", None)
scene.collection.objects.link(origin)


def volume_material(name, lobes, holes, density, shaved_bounds=None):
    volume = bpy.data.materials.new(name)
    volume.use_nodes = True
    nodes = volume.node_tree.nodes
    links = volume.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    scatter = nodes.new("ShaderNodeVolumePrincipled")
    scatter.inputs["Color"].default_value = (.91, .947, 1.0, 1)
    scatter.inputs["Anisotropy"].default_value = .29
    links.new(scatter.outputs["Volume"], output.inputs["Volume"])
    coordinates = nodes.new("ShaderNodeTexCoord")
    coordinates.object = origin
    position = coordinates.outputs["Object"]

    def assign(socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            links.new(value, socket)
        else:
            socket.default_value = value

    def math_node(operation, a, b):
        node = nodes.new("ShaderNodeMath")
        node.operation = operation
        assign(node.inputs[0], a)
        assign(node.inputs[1], b)
        return node.outputs[0]

    def vector(operation, a, b):
        node = nodes.new("ShaderNodeVectorMath")
        node.operation = operation
        assign(node.inputs[0], a)
        if b is not None:
            assign(node.inputs[1], b)
        return node.outputs["Value" if operation in ("LENGTH", "DOT_PRODUCT") else "Vector"]

    def noise(scale, detail, roughness):
        node = nodes.new("ShaderNodeTexNoise")
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = roughness
        links.new(position, node.inputs["Vector"])
        return node.outputs["Fac"]

    def ramp(value, minimum, maximum):
        node = nodes.new("ShaderNodeMapRange")
        node.interpolation_type = "SMOOTHERSTEP"
        assign(node.inputs["Value"], value)
        node.inputs["From Min"].default_value = minimum
        node.inputs["From Max"].default_value = maximum
        return node.outputs["Result"]

    def smooth_union(a, b, width):
        node = nodes.new("ShaderNodeMath")
        node.operation = "SMOOTH_MAX"
        assign(node.inputs[0], a)
        assign(node.inputs[1], b)
        assign(node.inputs[2], width)
        return node.outputs[0]

    field = None
    for center, radii in lobes:
        offset = vector("SUBTRACT", position, center)
        unit = vector("MULTIPLY", offset, tuple(1 / radius for radius in radii))
        lobe = math_node("SUBTRACT", 1.0, vector("LENGTH", unit, None))
        field = lobe if field is None else smooth_union(field, lobe, .35)

    curls = math_node("MULTIPLY", math_node("SUBTRACT", noise(5.3, 3.0, .67), .48), .85)
    turbulence = math_node("MULTIPLY", math_node("SUBTRACT", noise(17, 3, .64), .5), .28)
    weathered = math_node("ADD", field, math_node("ADD", curls, turbulence))
    core = ramp(weathered, -.04, .29)
    mist = math_node("MULTIPLY", ramp(weathered, -.29, .16), .085)
    mask = math_node("ADD", core, mist)
    for x, y, radius in holes:
        horizontal = vector("MULTIPLY", vector("SUBTRACT", position, (x, y, 0)), (1, 1, 0))
        distance = vector("LENGTH", horizontal, None)
        edge_noise = math_node("MULTIPLY", math_node("SUBTRACT", noise(23, 2, .6), .5), .034)
        edge = math_node("ADD", distance, edge_noise)
        mask = math_node("MULTIPLY", mask, ramp(edge, radius - .009, radius + .025))
    if shaved_bounds:
        x, y, z, radius, half_height, tilt = shaved_bounds
        offset = vector("SUBTRACT", position, (x, y, z))
        axis = (0, -math.sin(tilt), math.cos(tilt))
        axial = vector("DOT_PRODUCT", offset, axis)
        length = vector("LENGTH", offset, None)
        radial_squared = math_node("SUBTRACT", math_node("MULTIPLY", length, length),
                                   math_node("MULTIPLY", axial, axial))
        distance = math_node("SQRT", math_node("MAXIMUM", radial_squared, 0), 0)
        top_bottom = math_node("ABSOLUTE", axial, 0)
        curved_edge = math_node("MAXIMUM", math_node("SUBTRACT", distance, radius),
                               math_node("SUBTRACT", top_bottom, half_height))
        shaved = math_node("SUBTRACT", 1, ramp(curved_edge, -.035, .020))
        mask = math_node("MULTIPLY", mask, shaved)
    flecks = math_node("ADD", .54, math_node("MULTIPLY", noise(8.8, 3.5, .73), .76))
    thickness = math_node("MULTIPLY", mask, math_node("MULTIPLY", flecks, density))
    links.new(thickness, scatter.inputs["Density"])
    return volume


cloud_lobes = [
    ((x, y, z + head_lift), radii) for x, y, z, radii in [
        (.20, -.14, 1.145, (.57, .47, .22)),
        (.62, .20, 1.279, (.49, .45, .345)),
        (1.00, .57, 1.426, (.50, .40, .411)),
        (1.44, .645, 1.522, (.48, .411, .422)),
        (1.81, .607, 1.361, (.44, .343, .31)),
        (2.14, .570, 1.373, (.44, .405, .319)),
        (2.55, .408, 1.239, (.49, .432, .266)),
        (2.69, -.093, 1.164, (.34, .405, .206)),
        (2.43, -.488, 1.152, (.405, .345, .197)),
        (2.01, -.550, 1.128, (.405, .34, .173)),
        (1.61, -.56, 1.138, (.46, .315, .194)),
        (1.04, -.522, 1.136, (.50, .30, .183)),
        (.59, -.495, 1.132, (.384, .29, .167)),
        (1.73, -.027, 1.159, (.725, .52, .18)),
        (1.02, -.095, 1.151, (.53, .45, .169)),
        (2.35, -.08, 1.150, (.515, .45, .18)),
    ]
]
cloud = volume_material("Sunlit cumulus, sheared bores", cloud_lobes,
                        [(1.29, punch_y, .356), (2.19, punch_y, .356)], 26.0)
box("Cloud workpiece volume bounds", (1.25, .08, 1.36 + head_lift), (4.15, 2.45, 1.54), cloud, 0)

plug_y, plug_z = -.325, .791
plug_lobes = [
    ((punch_x, plug_y, plug_z), (.335, .332, .142)),
    ((punch_x - .13, plug_y - .11, plug_z - .045), (.22, .233, .087)),
    ((punch_x + .103, plug_y + .105, plug_z + .049), (.235, .225, .087)),
]
plug = volume_material("Falling cylindrical cloud offcut", plug_lobes, [], 32.0,
                       (punch_x, plug_y, plug_z, .288, .078, math.radians(19)))
box("Cloud offcut volume bounds", (punch_x, plug_y, plug_z), (.72, .72, .42), plug, 0)

# One seamless surface, three studio fixtures, and a long-lens catalog angle.
box("Studio sweep", (0, 0, -.083), (200, 200, .15), floor_mat, 0)

world = bpy.data.worlds.new("Soft neutral stage ambience")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (.78, .812, .87, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = .23
scene.world = world


def softbox(name, location, target, power, size, height, tint):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.energy = power
    data.size = size
    data.size_y = height
    data.color = tint
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


softbox("Large key through silk", (-3.4, -4.6, 6.9), (-.25, 0, 1.31),
        1250, 5.1, 3.6, (1, .925, .849))
softbox("Cool white frontal bounce", (4.7, -3.6, 4.45), (.54, 0, 1.36),
        375, 4.1, 3.8, (.855, .925, 1))
softbox("High rear strip for machined highlights", (1.4, 3.6, 5.6), (.35, 0, 1.45),
        1050, 4.0, 2.0, (1, .966, .922))
softbox("Backdrop bounce", (-.2, 6.8, 6.0), (0, 6.0, 0),
        790, 7.0, 4.3, (1, .959, .905))

camera_data = bpy.data.cameras.new("68 mm studio lens")
camera = bpy.data.objects.new("Three-quarter product camera", camera_data)
scene.collection.objects.link(camera)
target = Vector((.42, .06, 1.65))
camera.location = target + Vector((3.27, -8.70, 6.02))
camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
camera_data.lens = 68
scene.camera = camera

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = options.samples
scene.cycles.seed = 24
scene.cycles.use_denoising = True
scene.cycles.adaptive_threshold = .018 if options.samples > 40 else .04
scene.cycles.volume_step_rate = .57
scene.cycles.volume_max_steps = 512
scene.cycles.volume_bounces = 4
scene.cycles.transparent_max_bounces = 8
scene.cycles.max_bounces = 9
scene.render.resolution_x = options.size
scene.render.resolution_y = options.size
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "8"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = .20
scene.render.filepath = str(options.out.resolve())
bpy.ops.render.render(write_still=True)
