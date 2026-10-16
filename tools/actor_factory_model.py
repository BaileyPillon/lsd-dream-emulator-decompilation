"""Independent successful factory ownership plan; no native trace is an input.

This models object lifetimes, allocation arguments and ordered releases. It
does not predict complete object fields, geometry mappings or animation state.
"""
from dataclasses import dataclass, field
import struct

from tools import actor_child_model as child_model


@dataclass(eq=False)
class Node:
    pointer: int
    kind: str
    coordinate: int = 0
    state: int = 0
    coordinate_parent: object = None
    children: list = field(default_factory=list)
    parents: list = field(default_factory=list)


class OwnershipPlan:
    def __init__(self, raw, pool):
        raw = bytes(raw)
        self.raw, self.pool, self.events = raw, pool, []
        self.frame = child_model.decode_first_frame(raw)
        self.animations = struct.unpack_from('<I', raw, 16)[0]
        self.tmd = struct.unpack_from('<I', raw, 8)[0]
        self.objects = struct.unpack_from('<I', raw, self.tmd + 8)[0]
        # The independently initialized enumeration is required to give the
        # same result under both extreme residue patterns in this profile.
        count = self.frame.child_count
        zero = child_model.enumerate_types(self.frame.records, bytes(count))
        ones = child_model.enumerate_types(self.frame.records, b'\xff' * count)
        if zero != ones:
            raise ValueError('Residue-dependent enumeration is outside this ownership plan.')
        self.types = zero[0]
        animation_zero = 12 + struct.unpack_from('<I', raw, 20)[0]
        if animation_zero < 20 + self.animations * 4 or animation_zero + 16 > self.tmd:
            raise ValueError('Animation-zero header exceeds its bounded MOS extent.')
        cursor, self.commands = animation_zero + 16, []
        count = struct.unpack_from('<H', raw, animation_zero + 10)[0]
        for _ in range(count):
            if cursor + 4 > self.tmd:
                raise ValueError('Animation-zero command exceeds its MOS extent.')
            lead = struct.unpack_from('<I', raw, cursor)[0]
            words = lead >> 24
            if not words or cursor + words * 4 > self.tmd:
                raise ValueError('Invalid animation-zero command extent.')
            kind = lead >> 16 & 15
            if kind == 3 and words < 2:
                raise ValueError('A parent command has no payload.')
            self.commands.append((lead & 255, kind, raw[cursor + 4:cursor + words * 4]))
            cursor += words * 4

    def allocate(self, size):
        pointer = self.pool.allocate(size)
        if not pointer:
            raise ValueError('Allocation failure is outside the successful ownership plan.')
        self.events.append(('memory_allocate_mem', size, pointer))
        return pointer

    def release(self, pointer):
        result = self.pool.free(pointer)
        self.events.append(('memory_free_mem', pointer, result))

    def node(self, size, kind):
        node = Node(self.allocate(size), kind)
        node.coordinate, node.state = self.allocate(80), self.allocate(40)
        return node

    def attach(self, parent, child):
        parent.children.insert(0, (self.allocate(8), child))
        child.parents.insert(0, (self.allocate(8), parent))

    def remove(self, links, target):
        for index, (pointer, node) in enumerate(links):
            if node is target:
                self.release(pointer)
                del links[index]
                return

    def detach(self, parent, child):
        self.remove(parent.children, child)
        self.remove(child.parents, parent)

    def base_cleanup(self, node, notify=None):
        for _, parent in list(node.parents):
            self.detach(parent, node)
            if notify is not None:
                notify(parent)
        for _, child in list(node.children):
            self.detach(node, child)
        for pointer, _ in node.parents:
            self.release(pointer)
        node.parents.clear()

    def transform_cleanup(self, node):
        if node.coordinate_parent is not None:
            self.detach(node.coordinate_parent, node)
            node.coordinate_parent = None
        # Native Unk20 detaches coordinate descendants but does not destroy them.
        for _, child in list(node.children):
            if child.coordinate_parent is node:
                self.detach(node, child)
                child.coordinate_parent = None
        self.release(node.state)
        self.release(node.coordinate)
        self.base_cleanup(node)

    def create_model(self):
        model = Node(self.allocate(56), 'model')
        model.tmd = self.allocate(48)
        model.primitive_table = self.allocate((self.objects + 1) * 4)
        model.primitives = [self.allocate(36) for _ in range(self.objects)]
        model.parts = self.allocate(44)
        model.animations = [self.allocate(44) for _ in range(self.animations)]
        return model

    def create_actor(self, model=None):
        actor = self.node(152, 'actor')
        actor.owns_model = model is None
        actor.model = self.create_model() if model is None else model
        count = len(self.types)
        actor.child_table, actor.types = self.allocate(count * 4), self.allocate(count)
        actor.nodes = [self.node(88, 'child') for _ in range(count)]
        self.attach(actor, actor.model)
        for type_id, kind, payload in self.commands:
            if kind != 3 or type_id not in self.types:
                continue
            node = actor.nodes[self.types.index(type_id)]
            if node.coordinate_parent is not None:
                continue
            parent_id = struct.unpack_from('<I', payload)[0]
            if parent_id in (0, 0xFFFF):
                parent = actor
            else:
                if (parent_id & 255) not in self.types:
                    raise ValueError('A parent command references an absent child type.')
                parent = actor.nodes[self.types.index(parent_id & 255)]
            ancestor = parent
            while ancestor is not None:
                if ancestor is node:
                    raise ValueError('Cyclic coordinate parents are outside this ownership plan.')
                ancestor = ancestor.coordinate_parent
            node.coordinate_parent = parent
            self.attach(parent, node)
        return actor

    def destroy_actor(self, actor):
        for node in actor.nodes:
            self.transform_cleanup(node)
            self.release(node.pointer)
        self.release(actor.types)
        self.release(actor.child_table)
        if actor.owns_model:
            self.destroy_model(actor.model)
        self.transform_cleanup(actor)
        self.release(actor.pointer)

    def destroy_model(self, model):
        for part in model.animations:
            self.release(part)
        self.release(model.parts)
        for primitive in model.primitives:
            self.release(primitive)
        self.release(model.primitive_table)
        self.release(model.tmd)
        def on_notify(parent):
            if parent.kind == 'actor' and not parent.owns_model:
                self.destroy_actor(parent)
        self.base_cleanup(model, on_notify)
        self.release(model.pointer)

    def run(self, scenario):
        if scenario == 'owned':
            self.destroy_actor(self.create_actor())
        elif scenario in ('actor-first', 'model-first'):
            model = self.create_model()
            if scenario == 'actor-first':
                for _ in range(2):
                    self.destroy_actor(self.create_actor(model))
            else:
                self.create_actor(model)
            self.destroy_model(model)
        else:
            raise ValueError('Unknown ownership scenario.')
        if not (len(self.pool.blocks) == 1 and self.pool.blocks[0].free):
            raise ValueError('The ownership plan retained an allocation.')
        return self.events
