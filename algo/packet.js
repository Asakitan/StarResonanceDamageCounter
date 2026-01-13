const zlib = require("zlib");
const pb = require("./blueprotobuf");
const Long = require("long");
const pbjs = require("protobufjs/minimal");

class BinaryReader {
    constructor(buffer, offset = 0) {
        this.buffer = buffer;
        this.offset = offset;
    }

    readUInt64() {
        const value = this.buffer.readBigUInt64BE(this.offset);
        this.offset += 8;
        return value;
    }

    peekUInt64() {
        return this.buffer.readBigUInt64BE(this.offset);
    }

    readUInt32() {
        const value = this.buffer.readUInt32BE(this.offset);
        this.offset += 4;
        return value;
    }

    peekUInt32() {
        return this.buffer.readUInt32BE(this.offset);
    }

    readUInt16() {
        const value = this.buffer.readUInt16BE(this.offset);
        this.offset += 2;
        return value;
    }

    peekUInt16() {
        return this.buffer.readUInt16BE(this.offset);
    }

    readBytes(length) {
        const value = this.buffer.subarray(this.offset, this.offset + length);
        this.offset += length;
        return value;
    }

    peekBytes(length) {
        return this.buffer.subarray(this.offset, this.offset + length);
    }

    remaining() {
        return this.buffer.length - this.offset;
    }

    readRemaining() {
        const value = this.buffer.subarray(this.offset);
        this.offset = this.buffer.length;
        return value;
    }
}

const MessageType = {
    None: 0,
    Call: 1,
    Notify: 2,
    Return: 3,
    Echo: 4,
    FrameUp: 5,
    FrameDown: 6,
};

const NotifyMethod = {
    SyncNearEntities: 0x00000006,
    SyncNearDeltaInfo: 0x0000002d,
    SyncToMeDeltaInfo: 0x0000002e,
};

const AttrType = {
    AttrName: 0x01,
    AttrProfessionId: 0xdc,
    AttrFightPoint: 0x272e,
};

const ProfessionType = {
    雷影剑士: 1,
    冰魔导师: 2,
    涤罪恶火·战斧: 3,
    青岚骑士: 4,
    森语者: 5,
    雷霆一闪·手炮: 8,
    巨刃守护者: 9,
    暗灵祈舞·仪刀·仪仗: 10,
    神射手: 11,
    神盾骑士: 12,
    灵魂乐手: 13,
};

// 技能ID到职业的映射
const SKILL_TO_ROLE_MAP = {
    1241: "射线",
    55302: "协奏", 
    20301: "愈合",
    1518: "惩戒",
    2306: "狂音",
    120902: "冰矛",
    1714: "居合", 
    44701: "月刃",
    220112: "鹰弓",
    2203622: "鹰弓",
    1700827: "狼弓",
    1419: "空枪",
    1418: "重装",
    2405: "防盾",
    2406: "光盾", 
    199902: "岩盾",
};

// 根据技能ID获取职业名称
const getRoleFromSkill = (skillId) => {
    return SKILL_TO_ROLE_MAP[skillId] || null;
};

const getProfessionNameFromId = (professionId) => {
    switch (professionId) {
        case ProfessionType.雷影剑士:
            return "雷影剑士";
        case ProfessionType.冰魔导师:
            return "冰魔导师";
        case ProfessionType.涤罪恶火·战斧:
            return "涤罪恶火·战斧";
        case ProfessionType.青岚骑士:
            return "青岚骑士";
        case ProfessionType.森语者:
            return "森语者";
        case ProfessionType.雷霆一闪·手炮:
            return "雷霆一闪·手炮";
        case ProfessionType.巨刃守护者:
            return "巨刃守护者";
        case ProfessionType.暗灵祈舞·仪刀·仪仗:
            return "暗灵祈舞·仪刀/仪仗";
        case ProfessionType.神射手:
            return "神射手";
        case ProfessionType.神盾骑士:
            return "神盾骑士";
        case ProfessionType.灵魂乐手:
            return "灵魂乐手";
        default:
            return `未知职业(${professionId})`;  // 返回更有意义的信息
    }
};

const isUuidPlayer = (uuid) => {
    return (uuid.toBigInt() & 0xffffn) === 640n;
};

let currentUserUuid = Long.ZERO;

class PacketProcessor {
    constructor({ logger, userDataManager }) {
        this.logger = logger;
        this.userDataManager = userDataManager;
    }

    _decompressPayload(buffer) {
        if (!zlib.zstdDecompressSync) {
            this.logger.warn("zstdDecompressSync is not available! Please check your Node.js version!");
            return;
        }
        return zlib.zstdDecompressSync(buffer);
    }

    _processAoiSyncDelta(aoiSyncDelta) {
        if (!aoiSyncDelta) return;

        let targetUuid = aoiSyncDelta.Uuid;
        if (!targetUuid) return;
        const isTargetPlayer = isUuidPlayer(targetUuid);
        targetUuid = targetUuid.shiftRight(16);

        const skillEffect = aoiSyncDelta.SkillEffects;
        if (!skillEffect) return;

        if (!skillEffect.Damages) return;
        for (const syncDamageInfo of skillEffect.Damages) {
            const skillId = syncDamageInfo.OwnerId;
            if (!skillId) continue;

            let attackerUuid = syncDamageInfo.TopSummonerId || syncDamageInfo.AttackerUuid;
            if (!attackerUuid) continue;
            const isAttackerPlayer = isUuidPlayer(attackerUuid);
            attackerUuid = attackerUuid.shiftRight(16);

            const value = syncDamageInfo.Value;
            const luckyValue = syncDamageInfo.LuckyValue;
            const damage = value ?? luckyValue ?? Long.ZERO;
            if (damage.isZero()) continue;

            // syncDamageInfo.IsCrit doesn't seem to be set by server, use typeFlag instead
            // const isCrit = syncDamageInfo.IsCrit !== null ? syncDamageInfo.IsCrit : false;

            // TODO: from testing, first bit is set when there's crit, 3rd bit for lucky, require more testing here
            const isCrit = syncDamageInfo.TypeFlag != null ? (syncDamageInfo.TypeFlag & 1) === 1 : false;

            const isMiss = syncDamageInfo.IsMiss != null ? syncDamageInfo.IsMiss : false;
            const isHeal = syncDamageInfo.Type === pb.EDamageType.Heal;
            const isDead = syncDamageInfo.IsDead != null ? syncDamageInfo.IsDead : false;
            const isLucky = !!luckyValue;
            const hpLessenValue = syncDamageInfo.HpLessenValue != null ? syncDamageInfo.HpLessenValue : Long.ZERO;

            if (isTargetPlayer) {
                //玩家目标
                if (isHeal) {
                    //玩家被治疗
                    if (isAttackerPlayer) {
                        //只记录玩家造成的治疗
                        this.userDataManager.addHealing(attackerUuid.toNumber(), damage.toNumber(), isCrit, isLucky);
                        
                        // 尝试根据技能ID推断职业
                        const roleName = getRoleFromSkill(skillId);
                        if (roleName) {
                            this.userDataManager.setProfession(attackerUuid.toNumber(), roleName);
                            this.logger.debug(`Inferred profession ${roleName} from healing skill ${skillId} for player ${attackerUuid}`);
                        }
                    }
                } else {
                    //玩家受到伤害
                    this.userDataManager.addTakenDamage(targetUuid.toNumber(), damage.toNumber());
                }
            } else {
                //非玩家目标
                if (isHeal) {
                    //非玩家被治疗
                } else {
                    //非玩家受到伤害
                    if (isAttackerPlayer) {
                        //只记录玩家造成的伤害
                        this.userDataManager.addDamage(attackerUuid.toNumber(), skillId, damage.toNumber(), isCrit, isLucky, hpLessenValue.toNumber());
                        
                        // 尝试根据技能ID推断职业
                        const roleName = getRoleFromSkill(skillId);
                        if (roleName) {
                            this.userDataManager.setProfession(attackerUuid.toNumber(), roleName);
                            this.logger.debug(`Inferred profession ${roleName} from skill ${skillId} for player ${attackerUuid}`);
                        }
                    }
                }
            }

            let extra = [];
            if (isCrit) extra.push("Crit");
            if (isLucky) extra.push("Lucky");
            if (extra.length === 0) extra = ["Normal"];

            const actionType = isHeal ? "Healing" : "Damage";

            let infoStr = `Src: ${attackerUuid.toString()}`;
            if (isAttackerPlayer) {
                const attacker = this.userDataManager.getUser(attackerUuid.toNumber());
                if (attacker.name) {
                    infoStr = `Src: ${attacker.name}`;
                } else {
                    infoStr += " (player)";
                }
            }

            let targetName = `${targetUuid.toString()}`;
            if (isTargetPlayer) {
                const target = this.userDataManager.getUser(targetUuid.toNumber());
                if (target.name) {
                    targetName = target.name;
                } else {
                    targetName += " (player)"
                }
            }
            infoStr += ` Tgt: ${targetName}`;

            this.logger.info(`${infoStr} Skill/Buff: ${skillId} ${actionType}: ${damage} ${isHeal ? "" : ` HpLessen: ${hpLessenValue}`} Extra: ${extra.join("|")}`);
        }
    }

    _processSyncNearDeltaInfo(payloadBuffer) {
        const syncNearDeltaInfo = pb.SyncNearDeltaInfo.decode(payloadBuffer);
        // this.logger.debug(JSON.stringify(syncNearDeltaInfo, null, 2));

        if (!syncNearDeltaInfo.DeltaInfos) return;
        for (const aoiSyncDelta of syncNearDeltaInfo.DeltaInfos) {
            this._processAoiSyncDelta(aoiSyncDelta);
        }
    }

    _processSyncToMeDeltaInfo(payloadBuffer) {
        const syncToMeDeltaInfo = pb.SyncToMeDeltaInfo.decode(payloadBuffer);
        // this.logger.debug(JSON.stringify(syncToMeDeltaInfo, null, 2));

        const aoiSyncToMeDelta = syncToMeDeltaInfo.DeltaInfo;

        const uuid = aoiSyncToMeDelta.Uuid;
        if (uuid && !currentUserUuid.eq(uuid)) {
            currentUserUuid = uuid;
            this.logger.info("Got player UUID! UUID: " + currentUserUuid + " UID: " + currentUserUuid.shiftRight(16));
        }

        const aoiSyncDelta = aoiSyncToMeDelta.BaseDelta;
        if (!aoiSyncDelta) return;

        this._processAoiSyncDelta(aoiSyncDelta);
    }

    _processSyncNearEntities(payloadBuffer) {
        const syncNearEntities = pb.SyncNearEntities.decode(payloadBuffer);
        // this.logger.debug(JSON.stringify(syncNearEntities, null, 2));

        this.logger.debug(`SyncNearEntities: Appear count: ${syncNearEntities.Appear ? syncNearEntities.Appear.length : 0}`);
        
        if (!syncNearEntities.Appear) return;
        for (const entity of syncNearEntities.Appear) {
            this.logger.debug(`Entity type: ${entity.EntType}, UUID: ${entity.Uuid}`);
            
            if (entity.EntType !== pb.EEntityType.EntChar) {
                this.logger.debug(`Skipping non-character entity: ${entity.EntType} (EntChar = ${pb.EEntityType.EntChar})`);
                continue;
            }

            let playerUuid = entity.Uuid;
            if (!playerUuid) {
                this.logger.debug(`No UUID found for entity`);
                continue;
            }
            playerUuid = playerUuid.shiftRight(16);

            const attrCollection = entity.Attrs;
            if (!attrCollection) {
                this.logger.debug(`No attributes found for player UUID ${playerUuid}`);
                continue;
            }

            if (!attrCollection.Attrs) {
                this.logger.debug(`No Attrs array found for player UUID ${playerUuid}`);
                continue;
            }
            
            this.logger.debug(`Processing attributes for player UUID ${playerUuid}, found ${attrCollection.Attrs.length} attributes`);
            
            for (const attr of attrCollection.Attrs) {
                if (!attr.Id || !attr.RawData) {
                    this.logger.debug(`Invalid attribute: Id=${attr.Id}, RawData length=${attr.RawData ? attr.RawData.length : 0}`);
                    continue;
                }
                
                this.logger.debug(`Processing attribute ID: 0x${attr.Id.toString(16)} (${attr.Id}) for UUID ${playerUuid}`);
                
                const reader = pbjs.Reader.create(attr.RawData);

                switch (attr.Id) {
                    case AttrType.AttrName:
                        const playerName = reader.string();
                        this.userDataManager.setName(playerUuid.toNumber(), playerName);
                        this.logger.info(`Found player name ${playerName} for uuid ${playerUuid}`);
                        break;
                    case AttrType.AttrProfessionId:
                        const professionId = reader.int32();
                        const professionName = getProfessionNameFromId(professionId);
                        this.userDataManager.setProfession(playerUuid.toNumber(), professionName);
                        this.logger.info(`Found profession ${professionName} (ID: ${professionId}) for uuid ${playerUuid}`);
                        break;
                    case AttrType.AttrFightPoint:
                        const playerFightPoint = reader.int32();
                        this.userDataManager.setFightPoint(playerUuid.toNumber(), playerFightPoint);
                        this.logger.debug(`Found player fight point ${playerFightPoint} for uuid ${playerUuid}`);
                        break;
                    default:
                        this.logger.debug(`Found unknown attrId 0x${attr.Id.toString(16)} for uuid ${playerUuid}`);
                        break;
                }
            }
        }
    }

    _processNotifyMsg(reader, isZstdCompressed) {
        const serviceUuid = reader.readUInt64();
        const stubId = reader.readUInt32();
        const methodId = reader.readUInt32();

        if (serviceUuid !== 0x0000000063335342n) {
            this.logger.debug(`Skipping NotifyMsg with serviceId ${serviceUuid}`);
            return;
        }

        let msgPayload = reader.readRemaining();
        if (isZstdCompressed) {
            msgPayload = this._decompressPayload(msgPayload);
        }

        this.logger.debug(`Processing NotifyMsg with methodId ${methodId} (0x${methodId.toString(16)})`);
        
        switch (methodId) {
            case NotifyMethod.SyncNearEntities:
                this.logger.info(`Processing SyncNearEntities (methodId: ${methodId})`);
                this._processSyncNearEntities(msgPayload);
                break;
            case NotifyMethod.SyncToMeDeltaInfo:
                this._processSyncToMeDeltaInfo(msgPayload);
                break;
            case NotifyMethod.SyncNearDeltaInfo:
                this._processSyncNearDeltaInfo(msgPayload);
                break;
            default:
                this.logger.debug(`Skipping NotifyMsg with methodId ${methodId} (0x${methodId.toString(16)})`);
                break;
        }
        return;
    }

    _processReturnMsg(reader, isZstdCompressed) {
        this.logger.debug(`Unimplemented processing return`);
    }

    processPacket(packets) {
        try {
            const packetsReader = new BinaryReader(packets);

            do {
                let packetSize = packetsReader.peekUInt32();
                if (packetSize < 6) {
                    this.logger.debug(`Received invalid packet`);
                    return;
                }

                const packetReader = new BinaryReader(packetsReader.readBytes(packetSize));
                packetSize = packetReader.readUInt32(); // to advance
                const packetType = packetReader.readUInt16();
                const isZstdCompressed = packetType & 0x8000;
                const msgTypeId = packetType & 0x7fff;

                switch (msgTypeId) {
                    case MessageType.Notify:
                        this._processNotifyMsg(packetReader, isZstdCompressed);
                        break;
                    case MessageType.Return:
                        this._processReturnMsg(packetReader, isZstdCompressed);
                        break;
                    case MessageType.FrameDown:
                        const serverSequenceId = packetReader.readUInt32();
                        if (packetReader.remaining() == 0) break;

                        let nestedPacket = packetReader.readRemaining();

                        if (isZstdCompressed) {
                            nestedPacket = this._decompressPayload(nestedPacket);
                        }

                        // this.logger.debug("Processing FrameDown packet.");
                        this.processPacket(nestedPacket);
                        break;
                    default:
                        this.logger.debug(`Ignore packet with message type ${msgTypeId}.`);
                        break;
                }
            } while (packetsReader.remaining() > 0);
        } catch (e) {
            this.logger.debug(e);
        }
    }
}

module.exports = PacketProcessor;
