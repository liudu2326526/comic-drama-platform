const projects = [
  {
    name: "宫墙风云 第 12 章",
    summary:
      "当前文本适合生成“悬疑揭密 + 宫廷压迫感”节奏，建议前 4 个镜头快速立悬念，中段拉出追查关系，结尾保留追问。",
    story:
      "皇城夜雨，沈昭宁在冷宫废井旁发现一枚染血玉佩。她意识到失踪三年的太子旧案并未终结，而今夜的巡城火光与宫门异动，正把她一步步推回权力漩涡。她必须在天亮前找出玉佩真正的主人，否则自己将被当成旧案余党一并清除。",
    characters: [
      {
        name: "沈昭宁",
        role: "主角",
        summary: "主角 · 冷感宫廷调查者 · 8 镜头复用",
        description:
          "沈昭宁，21 岁，清冷克制的宫廷旧案调查者，黑发高束，青灰宫装带少量朱砂纹样，面部线条利落，眼神警惕、带压抑感，国风漫感写意风格。",
        meta: [
          "主视角：左 45 度半身与正脸特写",
          "动态特征：走入雨幕、停步、垂眼观察",
          "一致性约束：发型、服饰、青灰色调不可漂移"
        ]
      },
      {
        name: "裴景珩",
        role: "关键配角",
        summary: "关键配角 · 旧案关联人 · 3 镜头复用",
        description:
          "裴景珩，24 岁，外冷内压的东宫旧部，墨发束冠，深青近黑官袍，肩线挺直，神情疏离克制，适合以逆光或半明半暗构图强化复杂立场。",
        meta: [
          "主视角：正脸静态与侧身回望",
          "动态特征：驻足、回身、压低声线对话",
          "一致性约束：高束发冠、深色官袍、冷淡神态保持稳定"
        ]
      },
      {
        name: "秦姑姑",
        role: "氛围配角",
        summary: "氛围配角 · 冷宫看守者 · 2 镜头复用",
        description:
          "秦姑姑，45 岁上下，身形消瘦，旧宫服发暗，眼下有疲态，带熟悉冷宫规则的沉默感，适合放在边角构图中强化宫廷压抑氛围。",
        meta: [
          "主视角：半身侧脸和门框内窥视",
          "动态特征：提灯、缓慢转头、压低肩背",
          "一致性约束：暗色旧宫服、疲惫神态、低存在感"
        ]
      }
    ],
    scenes: [
      {
        name: "冷宫废院",
        summary: "主场景 · 夜景悬疑 · 复用 4 镜头",
        usage: "复用 4 镜头",
        theme: "theme-palace",
        description:
          "冷宫废院夜景，残破高墙、湿石地面、废井、微弱宫灯与斜落雨丝构成空旷压抑空间，整体以青灰冷色为主，局部点缀暖橙火光。",
        meta: [
          "空间关系：左后方高墙，中部废井，右侧入场路径",
          "动态元素：斜雨、灯火晃动、远处巡城火光",
          "一致性约束：夜景冷色、废院结构与井位固定"
        ]
      },
      {
        name: "东宫长廊",
        summary: "回忆场景 · 权力压迫 · 复用 2 镜头",
        usage: "复用 2 镜头",
        theme: "theme-palace",
        description:
          "东宫长廊夜色，漆柱、宫灯、长影和封闭透视构成权力感空间，整体冷金与墨青混合，适合人物对峙与回忆式插入镜头。",
        meta: [
          "空间关系：纵深长廊、两侧柱列、尽头宫门",
          "动态元素：烛影摇晃、衣摆掠动、远处脚步声",
          "一致性约束：长廊透视、宫灯位置、压迫式构图稳定"
        ]
      },
      {
        name: "宫门外火道",
        summary: "外部危机场景 · 火光逼近 · 复用 3 镜头",
        usage: "复用 3 镜头",
        theme: "theme-palace",
        description:
          "宫门外火道被巡城火把照亮，石阶、城门、甲兵剪影与夜雾形成紧张边界感，适合制造天亮前追逼感。",
        meta: [
          "空间关系：前景火把，中景甲兵，后景高门",
          "动态元素：火焰晃动、甲胄反光、薄雾推进",
          "一致性约束：城门轮廓、火光方向、队列密度固定"
        ]
      }
    ]
  },
  {
    name: "星轨学院 序章",
    summary:
      "更适合做“世界观展示 + 少年登场”的轻冒险节奏，镜头数可以压缩，重点做学院入口、星图装置与主角初登场。",
    story:
      "凌晨的星轨学院漂浮在海雾之上，少年林澈第一次看见悬空星环启动。传说中失控的观星仪在今夜重新亮起，也把他卷入一场关于学院禁术的试炼。",
    characters: [
      {
        name: "林澈",
        role: "主角",
        summary: "主角 · 学院新生 · 5 镜头复用",
        description:
          "林澈，17 岁，少年感强，短发，学院制服带银蓝细节，眼神明亮但略带迟疑，科幻校园漫画风，动作轻快，有初入未知世界的好奇心。",
        meta: [
          "主视角：正脸近景和奔跑半身",
          "动态特征：抬头、快步靠近、伸手触碰装置",
          "一致性约束：制服银蓝细节、少年感、明亮眼神稳定"
        ]
      },
      {
        name: "岑教授",
        role: "导师角色",
        summary: "导师角色 · 权威引导者 · 2 镜头复用",
        description:
          "岑教授，40 岁左右，白金短发，学院长袍带环形纹理，气质冷静理性，适合在装置光线下出现，强化权威与未知规则感。",
        meta: [
          "主视角：中景站姿与装置前正面",
          "动态特征：抬手示意、缓慢转身、光中静立",
          "一致性约束：长袍轮廓、白金发色、理性神情保持一致"
        ]
      }
    ],
    scenes: [
      {
        name: "学院入口",
        summary: "主场景 · 未来学院 · 复用 3 镜头",
        usage: "复用 3 镜头",
        theme: "theme-academy",
        description:
          "高空学院入口，雾海、悬桥、旋转星环与冷白能量流构成开阔空间，整体偏蓝银色，具有未来学院的秩序感与神秘感。",
        meta: [
          "空间关系：前景悬桥，中景入口，后景雾海与星环",
          "动态元素：能量流、薄雾漂移、星环缓慢旋转",
          "一致性约束：蓝银主色、入口比例、星环位置固定"
        ]
      },
      {
        name: "星图装置厅",
        summary: "核心装置场景 · 世界观展示 · 复用 2 镜头",
        usage: "复用 2 镜头",
        theme: "theme-academy",
        description:
          "圆形装置大厅内悬浮星图，地面刻度与能量纹路形成强中心构图，适合做主角初次触碰超常力量的关键镜头。",
        meta: [
          "空间关系：中央星图、环形台阶、上方穹顶",
          "动态元素：星图旋转、光粒上浮、纹路点亮",
          "一致性约束：中心装置比例、蓝白发光节奏、环形结构稳定"
        ]
      }
    ]
  },
  {
    name: "夜港异闻录 第 3 集",
    summary:
      "当前章节更适合“人物对峙 + 港口异象”的多段推进节奏，后半段可增加风暴前压迫感和霓虹港区的空间变化。",
    story:
      "夜港的风暴还未抵达，顾行舟已在码头尽头看见失踪渔船的灯牌。潮水中浮起的不只是船骸，还有一段被封存多年的海上交易秘密。",
    characters: [
      {
        name: "顾行舟",
        role: "主角",
        summary: "主角 · 港口侦查员 · 6 镜头复用",
        description:
          "顾行舟，28 岁，硬朗沉稳，深色风衣、防水靴、短发，脸部轮廓清晰，港口侦查员气质，写实漫感混合风格，动作控制感强。",
        meta: [
          "主视角：雨夜半身、码头逆光和侧脸近景",
          "动态特征：抬灯、俯身观察、迎风站定",
          "一致性约束：深色风衣、硬朗轮廓、低调压迫神情稳定"
        ]
      },
      {
        name: "岑暮",
        role: "对峙角色",
        summary: "对峙角色 · 海上交易中间人 · 3 镜头复用",
        description:
          "岑暮，30 岁左右，短卷发，深红衬衫外搭防风外套，笑意克制但危险，适合放在霓虹反光和海雾里塑造不可信任感。",
        meta: [
          "主视角：侧脸抽烟与对峙半身",
          "动态特征：缓笑、抬眼、手指敲击栏杆",
          "一致性约束：红色内搭、危险笑意、霓虹反光环境稳定"
        ]
      }
    ],
    scenes: [
      {
        name: "夜港码头",
        summary: "主场景 · 工业悬疑 · 复用 4 镜头",
        usage: "复用 4 镜头",
        theme: "theme-harbor",
        description:
          "夜港码头，潮湿钢架、远处霓虹、低压乌云与摇晃水面构成工业悬疑感，整体深蓝偏绿，局部霓虹洋红和船灯黄光作为反差。",
        meta: [
          "空间关系：前景钢架，中景水面，后景霓虹港区",
          "动态元素：水面反光、雾气、吊臂微晃",
          "一致性约束：深蓝偏绿基调、港区钢架、霓虹方向稳定"
        ]
      },
      {
        name: "失踪渔船甲板",
        summary: "关键证据场景 · 封闭压迫 · 复用 2 镜头",
        usage: "复用 2 镜头",
        theme: "theme-harbor",
        description:
          "渔船甲板狭窄潮湿，破损绳网、旧灯牌和风暴前湿冷空气共同构成近距离压迫感，适合证据发现与人物对峙镜头。",
        meta: [
          "空间关系：窄甲板、左侧绳网、后方驾驶舱",
          "动态元素：船体轻晃、灯牌闪烁、海风掀动衣摆",
          "一致性约束：甲板尺度、灯牌位置、潮湿质感稳定"
        ]
      }
    ]
  }
];

const projectList = document.getElementById("projectList");
const projectName = document.getElementById("projectName");
const projectSummary = document.getElementById("projectSummary");
const storyInput = document.getElementById("storyInput");
const characterList = document.getElementById("characterList");
const characterCount = document.getElementById("characterCount");
const characterName = document.getElementById("characterName");
const characterRole = document.getElementById("characterRole");
const characterString = document.getElementById("characterString");
const characterMeta = document.getElementById("characterMeta");
const sceneList = document.getElementById("sceneList");
const sceneCount = document.getElementById("sceneCount");
const sceneReuseTag = document.getElementById("sceneReuseTag");
const sceneName = document.getElementById("sceneName");
const sceneLensUsage = document.getElementById("sceneLensUsage");
const sceneString = document.getElementById("sceneString");
const sceneMeta = document.getElementById("sceneMeta");
const sceneStage = document.getElementById("sceneStage");

let currentProjectIndex = 0;
let currentCharacterIndex = 0;
let currentSceneIndex = 0;

function renderMetaList(target, items) {
  target.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderCharacterList(project) {
  characterCount.textContent = `${project.characters.length} 个资产`;
  characterList.innerHTML = project.characters
    .map(
      (character, index) => `
        <button class="asset-list-item ${index === currentCharacterIndex ? "active" : ""}" data-character-index="${index}">
          <strong>${character.name}</strong>
          <small>${character.summary}</small>
        </button>
      `
    )
    .join("");
}

function renderSceneList(project) {
  sceneCount.textContent = `${project.scenes.length} 个资产`;
  sceneList.innerHTML = project.scenes
    .map(
      (scene, index) => `
        <button class="asset-list-item ${index === currentSceneIndex ? "active" : ""}" data-scene-index="${index}">
          <strong>${scene.name}</strong>
          <small>${scene.summary}</small>
        </button>
      `
    )
    .join("");
}

function updateCharacterDetail(project) {
  const character = project.characters[currentCharacterIndex];
  characterName.textContent = character.name;
  characterRole.textContent = character.role;
  characterString.textContent = character.description;
  renderMetaList(characterMeta, character.meta);

  document.querySelectorAll("[data-character-index]").forEach((button, index) => {
    button.classList.toggle("active", index === currentCharacterIndex);
  });
}

function updateSceneDetail(project) {
  const scene = project.scenes[currentSceneIndex];
  sceneName.textContent = scene.name;
  sceneReuseTag.textContent = scene.usage;
  sceneLensUsage.textContent = scene.usage;
  sceneString.textContent = scene.description;
  renderMetaList(sceneMeta, scene.meta);

  sceneStage.classList.remove("theme-palace", "theme-academy", "theme-harbor");
  sceneStage.classList.add(scene.theme);

  document.querySelectorAll("[data-scene-index]").forEach((button, index) => {
    button.classList.toggle("active", index === currentSceneIndex);
  });
}

function updateProject(index) {
  const data = projects[index];
  currentProjectIndex = index;
  currentCharacterIndex = 0;
  currentSceneIndex = 0;

  projectName.textContent = data.name;
  projectSummary.textContent = data.summary;
  storyInput.value = data.story;

  renderCharacterList(data);
  renderSceneList(data);
  updateCharacterDetail(data);
  updateSceneDetail(data);

  document.querySelectorAll(".project-card").forEach((card, cardIndex) => {
    card.classList.toggle("active", cardIndex === index);
  });
}

projectList?.addEventListener("click", (event) => {
  const button = event.target.closest(".project-card");
  if (!button) {
    return;
  }

  const index = Number(button.dataset.project);
  if (Number.isNaN(index)) {
    return;
  }

  updateProject(index);
});

characterList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-character-index]");
  if (!button) {
    return;
  }

  const index = Number(button.dataset.characterIndex);
  if (Number.isNaN(index)) {
    return;
  }

  currentCharacterIndex = index;
  updateCharacterDetail(projects[currentProjectIndex]);
});

sceneList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-scene-index]");
  if (!button) {
    return;
  }

  const index = Number(button.dataset.sceneIndex);
  if (Number.isNaN(index)) {
    return;
  }

  currentSceneIndex = index;
  updateSceneDetail(projects[currentProjectIndex]);
});

updateProject(0);
