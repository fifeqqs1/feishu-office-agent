<script setup lang="ts">
import { onMounted, ref, watch, computed } from "vue"
import { useRouter } from "vue-router"
import { useRoute } from "vue-router"
import { ElMessage, ElMessageBox } from 'element-plus'
import workspaceIcon from '../assets/workspace.svg'
import applicationCenterIcon from '../assets/application-center.svg'
import dialogIcon from '../assets/dialog.svg'
import robotIcon from '../assets/robot.svg'
import pluginIcon from '../assets/plugin.svg'
import knowledgeIcon from '../assets/knowledge.svg'
import modelIcon from '../assets/model.svg'
import mcpIcon from '../assets/mcp.svg'
import skillIcon from '../assets/skill.svg'
import { User, SwitchButton, Setting } from '@element-plus/icons-vue'
import { useAgentCardStore } from "../store/agent_card"
import { useUserStore } from "../store/user"
import { getAgentsAPI } from "../apis/agent"
import { logoutAPI, getUserInfoAPI } from "../apis/auth"
import { Agent } from "../type"

const agentCardStore = useAgentCardStore()
const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const itemName = ref("饺子 Agent 平台")
const showAppCenterMenu = ref(false)
let appCenterHoverTimer: any = null

const openAppCenterMenu = () => {
  if (appCenterHoverTimer) clearTimeout(appCenterHoverTimer)
  showAppCenterMenu.value = true
}

const closeAppCenterMenu = () => {
  if (appCenterHoverTimer) clearTimeout(appCenterHoverTimer)
  appCenterHoverTimer = setTimeout(() => {
    showAppCenterMenu.value = false
  }, 120)
}

const goWorkspaceTop = () => {
  router.push('/workspace')
}

const appCenterColumns = ref([
  [
    { label: '聊天', icon: dialogIcon, route: '/conversation' },
    { label: '任务', icon: workspaceIcon, route: '/workspace' }
  ],
  [
    { label: '代理', icon: robotIcon, route: '/agent' },
    { label: '插件', icon: pluginIcon, route: '/tool' }
  ],
  [
    { label: '知识', icon: knowledgeIcon, route: '/knowledge' },
    { label: '模型', icon: modelIcon, route: '/model' }
  ],
  [
    { label: '协议', icon: mcpIcon, route: '/mcp-server' },
    { label: '技能', icon: skillIcon, route: '/agent-skill' }
  ]
])
const current = ref(route.meta.current)
const cardList = ref<Agent[]>([])

// 顶栏按钮激活态
const isWorkspaceActive = computed(() => route.path.startsWith('/workspace'))
const isAppCenterActive = computed(() => route.path.startsWith('/homepage'))

// 初始化用户状态
onMounted(async () => {
  userStore.initUserState()
  
  // 如果已登录但没有头像，则尝试获取用户信息
  if (userStore.isLoggedIn && userStore.userInfo && !userStore.userInfo.avatar) {
    try {
      const response = await getUserInfoAPI(userStore.userInfo.id)
      if (response.data.status_code === 200 && response.data.data) {
        const userData = response.data.data
        userStore.updateUserInfo({
          avatar: userData.user_avatar || userData.avatar || '/src/assets/user.svg',
          description: userData.user_description || userData.description
        })
      }
    } catch (error) {
      console.error('初始化时获取用户信息失败:', error)
    }
  }
  
  updateList()
})

const godefault = () => {
  agentCardStore.clear()
  router.push("/")
}
  
const updateList = async () => {
  try {
    const response = await getAgentsAPI()
    cardList.value = response.data.data
  } catch (error) {
    console.error('获取智能体列表失败:', error)
  }
}

const goCurrent = (item: string) => {
  const routes: Record<string, string> = {
    "homepage": "/homepage",
    "conversation": "/conversation",
    "agent": "/agent",
    "mcp-server": "/mcp-server",
    "knowledge": "/knowledge",
    "tool": "/tool",
    "agent-skill": "/agent-skill",
    "model": "/model",
    "workspace": "/workspace",
    "dashboard": "/dashboard"
  }
  
  router.push(routes[item] || "/")
}

// 用户下拉菜单命令处理
const handleUserCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'settings':
      router.push('/configuration')
      break
    case 'logout':
      await handleLogout()
      break
  }
}

// 退出登录
const handleLogout = async () => {
  try {
    await logoutAPI()
  } catch (error) {
    console.error('调用登出接口失败:', error)
  }
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 头像加载错误处理
const handleAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement
  if (target) {
    target.src = '/src/assets/user.svg'
  }
}

watch(
  route,
  (val) => {
    current.value = route.meta.current
  },
  {
    immediate: true
  }
)
</script>

<template>
  <div class="ai-body">
    <div class="ai-nav">
      <div class="left">
        <div class="item-img" @click="godefault">
          <img :src="robotIcon" alt="Logo" class="logo" />
        </div>
        <div class="nav-links">
          <img src="../assets/agentchat.svg" alt="智言平台" class="brand-logo-img" />
        </div>
      </div>
      <div class="right">
        <!-- 用户信息区域 -->
        <div class="user-info">
          <el-dropdown @command="handleUserCommand" trigger="click">
            <div class="user-avatar-wrapper">
              <div class="user-avatar">
                <img
                  :src="userStore.userInfo?.avatar || '/src/assets/user.svg'"
                  alt="用户头像"
                  style="width: 40px; height: 40px; border-radius: 50%"
                  @error="handleAvatarError"
                  referrerpolicy="no-referrer"
                />
              </div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile" :icon="User">
                  个人资料
                </el-dropdown-item>
<!--                <el-dropdown-item command="settings" :icon="Setting">-->
<!--                  系统设置-->
<!--                </el-dropdown-item>-->
                <el-dropdown-item divided command="logout" :icon="SwitchButton">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>
    <div class="ai-main">
      <el-col :span="2">
        <div class="sidebar-content">
          <el-menu
            active-text-color="#6b9eff"
            background-color="#f4f5f8"
            class="el-menu-vertical-demo"
            :default-active="current"
            text-color="#909399"
          >
            <el-menu-item index="workspace" @click="goCurrent('workspace')">
              <template #title>
                <el-icon>
                  <img src="../assets/workspace.svg" width="22px" height="22px" />
                </el-icon>
                <span>工作台</span>
              </template>
            </el-menu-item>
            <el-menu-item index="homepage" @click="goCurrent('homepage')">
              <template #title>
                <el-icon>
                  <img src="../assets/explore.svg" width="22px" height="22px" />
                </el-icon>
                <span>探索</span>
              </template>
            </el-menu-item>
            <el-menu-item index="conversation" @click="goCurrent('conversation')">
              <template #title>
                <el-icon>
                  <img src="../assets/dialog.svg" width="22px" height="22px" />
                </el-icon>
                <span>会话</span>
              </template>
            </el-menu-item>
            <el-menu-item index="agent" @click="goCurrent('agent')">
              <template #title>
                <el-icon>
                  <img src="../assets/robot.svg" width="22px" height="22px" />
                </el-icon>
                <span>智能体</span>
              </template>
            </el-menu-item>
            <el-menu-item index="mcp-server" @click="goCurrent('mcp-server')">
              <template #title>
                <el-icon>
                  <img src="../assets/mcp.svg" width="22px" height="22px" />
                </el-icon>
                <span>MCP</span>
              </template>
            </el-menu-item>
            <el-menu-item index="knowledge" @click="goCurrent('knowledge')">
              <template #title>
                <el-icon>
                  <img src="../assets/knowledge.svg" width="22px" height="22px" />
                </el-icon>
                <span>知识库</span>
              </template>
            </el-menu-item>
            <el-menu-item index="tool" @click="goCurrent('tool')">
              <template #title>
                <el-icon>
                  <img src="../assets/plugin.svg" width="22px" height="22px" />
                </el-icon>
                <span>工具</span>
              </template>
            </el-menu-item>
            <el-menu-item index="agent-skill" @click="goCurrent('agent-skill')">
              <template #title>
                <el-icon>
                  <img src="../assets/skill.svg" width="22px" height="22px" />
                </el-icon>
                <span>Skill</span>
              </template>
            </el-menu-item>
            <el-menu-item index="model" @click="goCurrent('model')">
              <template #title>
                <el-icon>
                  <img src="../assets/model.svg" width="22px" height="22px" />
                </el-icon>
                <span>模型</span>
              </template>
            </el-menu-item>
            <el-menu-item index="dashboard" @click="goCurrent('dashboard')">
              <template #title>
                <el-icon>
                  <img src="../assets/dashboard.svg" width="22px" height="22px" />
                </el-icon>
                <span>数据看板</span>
              </template>
            </el-menu-item>
          </el-menu>
        </div>
      </el-col>
      <div class="content">
        <router-view></router-view>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.ai-body {
  overflow: hidden;
  background-color: #fff9f2;
  color: #5c3d2e;

  .ai-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 64px;
    background: #ffffff;
    padding: 0 24px;
    box-shadow: 0 1px 4px rgba(255, 159, 67, 0.1);
    position: relative;
    z-index: 3000;

    .left {
      display: flex;
      align-items: center;
      font-weight: 600;
      color: #5c3d2e;
      cursor: pointer;
      transition: all 0.3s ease;

      &:hover {
        opacity: 0.8;
      }

      .item-img {
        margin-right: 0;

        .logo {
          width: 32px;
          height: 32px;
          filter: drop-shadow(0 0 5px rgba(255, 159, 67, 0.4));
          transition: all 0.3s ease;
        }
      }

      .nav-links {
        display: flex;
        align-items: center;
        margin-left: 8px;
        gap: 10px;

        .brand-logo-img {
          height: 45px;
          width: auto;
          display: block;
          filter: drop-shadow(0 2px 6px rgba(255, 159, 67, 0.3));
          user-select: none;
        }
      }
    }

    .right {
      display: flex;
      align-items: center;
      gap: 20px;

      .user-info {
        display: flex;
        align-items: center;
        gap: 12px;

        .user-avatar-wrapper {
          cursor: pointer;

          .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            overflow: hidden;
            border: 2px solid #ff9f43;
            box-shadow: 0 2px 8px rgba(255, 159, 67, 0.2);
            transition: all 0.3s ease;

            &:hover {
              transform: scale(1.1);
              box-shadow: 0 4px 12px rgba(255, 159, 67, 0.3);
            }
          }
        }
      }
    }
  }

  .ai-main {
    display: flex;
    height: calc(100vh - 64px);
    background-color: #fff9f2;

    .sidebar-content {
      height: 100%;
      background-color: #ffffff;
      border-right: 1px solid #ffe0b2;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: width 0.3s ease;

      .el-menu {
        border-right: none;
        background-color: #ffffff;

        .el-menu-item {
          height: 50px;
          line-height: 50px;
          font-size: 14px;
          font-weight: 500;
          color: #8d6e63;

          &.is-active {
            background-color: #fff3e0 !important;
            color: #ff9f43 !important;
            border-right: 3px solid #ff9f43;
          }

          &:hover {
            background-color: #fff8f0;
            color: #ff9f43;
          }

          .el-icon {
            margin-right: 10px;
          }
        }
      }

      .sidebar-footer {
        padding: 16px;
        border-top: 1px solid #ffe0b2;

        .help-links {
          display: flex;
          justify-content: center;
          gap: 20px;

          .help-link {
            .help-icon {
              width: 24px;
              height: 24px;
              opacity: 0.6;
              transition: opacity 0.3s ease;
              /* filter updated to a brownish orange color */
              filter: sepia(100%) saturate(300%) hue-rotate(350deg) brightness(80%);

              &:hover {
                opacity: 1;
              }
            }
          }
        }
      }
    }

    .content {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      background-color: #fff9f2;
    }
  }
}
</style>
