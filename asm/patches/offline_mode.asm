; Code that is only applied to offline seeds (seeds generated without an Archipelago .aptww file).
; In offline mode the items placed in the world are given to the player directly when picked up, so item get functions
; need to handle progressive items themselves instead of relying on the Archipelago client to pick the right item.
.open "sys/main.dol"
.org @NextFreeSpace
; The Archipelago branch split the magic meter item get into two functions (normal and upgrade) and lets the client decide
; which one to call. Offline, both magic meter item IDs give the next magic meter level instead.
.global progressive_magic_meter_item_func
progressive_magic_meter_item_func:
; Function start stuff
stwu sp, -0x10 (sp)
mflr r0
stw r0, 0x14 (sp)


lis r3, 0x803C4C1B@ha
addi r3, r3, 0x803C4C1B@l
lbz r4, 0 (r3) ; Max magic meter
cmpwi r4, 0
beq progressive_magic_meter_item_func_get_normal_magic_meter
cmpwi r4, 16
beq progressive_magic_meter_item_func_get_magic_meter_upgrade
b progressive_magic_meter_item_func_end

progressive_magic_meter_item_func_get_normal_magic_meter:
bl normal_magic_meter_item_func
b progressive_magic_meter_item_func_end

progressive_magic_meter_item_func_get_magic_meter_upgrade:
bl item_func_max_mp_up1__Fv


progressive_magic_meter_item_func_end:
; Function end stuff
lwz r0, 0x14 (sp)
mtlr r0
addi sp, sp, 0x10
blr
.close
