<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, SwitchButton, Setting } from '@element-plus/icons-vue'
import workspaceIcon from '../../assets/workspace.svg'
import applicationCenterIcon from '../../assets/application-center.svg'
import dialogIcon from '../../assets/dialog.svg'
import robotIcon from '../../assets/robot.svg'
import pluginIcon from '../../assets/plugin.svg'
import knowledgeIcon from '../../assets/knowledge.svg'
import modelIcon from '../../assets/model.svg'
import mcpIcon from '../../assets/mcp.svg'
import { useUserStore } from '../../store/user'
import { logoutAPI, getUserInfoAPI } from '../../apis/auth'
import { 
  getWorkspaceSessionsAPI, 
  deleteWorkspaceSessionAPI 
} from '../../apis/workspace'

const router = useRouter()
import { useRoute } from 'vue-router'
const route = useRoute()
const userStore = useUserStore()
const selectedSession = ref('')
const sessions = ref<any[]>([])
const loading = ref(false)

// 格式化时间
const formatTime = (timeStr: string) => {
  try {
    if (!timeStr) return '未知时间'
    
    const date = new Date(timeStr)
    if (isNaN(date.getTime())) {
      return '未知时间'
    }
    
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
    
    if (diffInHours < 1) return '刚刚'
    if (diffInHours < 24) return `${Math.floor(diffInHours)}小时前`
    if (diffInHours < 24 * 7) return `${Math.floor(diffInHours / 24)}天前`
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch (error) {
    return '未知时间'
  }
}

// 获取会话列表
const fetchSessions = async () => {
  try {
    loading.value = true
    const response = await getWorkspaceSessionsAPI()
    if (response.data.status_code === 200) {
      sessions.value = response.data.data.map((session: any) => ({
        sessionId: session.session_id || session.id,
        title: session.title || '未命名会话',
        createTime: session.create_time || session.created_at || new Date().toISOString(),
        agent: session.agent || 'lingseek', // 保存agent类型，默认为lingseek
        contexts: session.contexts || [] // 保存上下文
      }))
      console.log('工作区会话列表:', sessions.value)
    } else {
      ElMessage.error('获取会话列表失败')
    }
  } catch (error) {
    console.error('获取会话列表出错:', error)
    ElMessage.error('获取会话列表失败')
  } finally {
    loading.value = false
  }
}

// 删除会话
const deleteSession = async (sessionId: string, event: Event) => {
  event.stopPropagation()
  
  try {
    const response = await deleteWorkspaceSessionAPI(sessionId)
    if (response.data.status_code === 200) {
      ElMessage.success('会话删除成功')
      await fetchSessions()
      
      if (selectedSession.value === sessionId) {
        selectedSession.value = ''
        router.push('/workspace')
      }
    } else {
      ElMessage.error('删除会话失败')
    }
  } catch (error) {
    console.error('删除会话出错:', error)
    ElMessage.error('删除会话失败')
  }
}

// 选择会话 - 根据agent类型跳转到不同页面
const selectSession = (sessionId: string) => {
  selectedSession.value = sessionId
  
  // 找到对应的会话
  const session = sessions.value.find(s => s.sessionId === sessionId)
  
  if (!session) {
    console.error('未找到会话:', sessionId)
    return
  }
  
  console.log('选择会话:', sessionId, '类型:', session.agent)
  
  // 根据agent类型判断跳转页面
  if (session.agent === 'simple') {
    // 日常模式，跳转到日常对话页面，并传递session_id
    router.push({
      name: 'workspaceDefaultPage',
      query: {
        session_id: sessionId
      }
    })
  } else {
    // lingseek模式，跳转到三列布局页面
    router.push({
      name: 'taskGraphPage',
      query: {
        session_id: sessionId
      }
    })
  }
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

// 跳转到应用中心
const goToHomepage = () => {
  router.push('/homepage')
}

// 跳转到工作台（当前页）
const goToWorkspace = () => {
  router.push('/workspace')
}

// 应用中心下拉（与首页保持一致）
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

const appCenterColumns = ref([
  [
    { label: '会话', icon: dialogIcon, route: '/conversation' },
    { label: '工作台', icon: workspaceIcon, route: '/workspace' }
  ],
  [
    { label: '智能体', icon: robotIcon, route: '/agent' },
    { label: '工具', icon: pluginIcon, route: '/tool' }
  ],
  [
    { label: '知识库', icon: knowledgeIcon, route: '/knowledge' },
    { label: '模型', icon: modelIcon, route: '/model' }
  ],
  [
    { label: 'MCP', icon: mcpIcon, route: '/mcp-server' }
  ]
])

// 顶栏按钮激活态（工作台页自身）
const isWorkspaceActive = computed(() => route.path.startsWith('/workspace'))
const isAppCenterActive = computed(() => route.path.startsWith('/homepage'))

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
  
  await fetchSessions()
})
</script>

<template>
  <div class="workspace-container">
    <!-- 顶部导航栏 -->
    <div class="workspace-nav">
      <div class="nav-left">
        <div class="logo-section">
          <img src="../../assets/robot.svg" alt="Logo" class="logo" />
        </div>
        <div class="nav-links">
          <img src="../../assets/agentchat.svg" alt="饺子 Agent 平台" class="brand-logo-img" />
        </div>
      </div>
      <div class="nav-right">
        <!-- 用户信息区域 -->
        <div class="user-info">
          <el-dropdown @command="handleUserCommand" trigger="click">
            <div class="user-avatar-wrapper">
              <div class="user-avatar">
                <img
                  :src="userStore.userInfo?.avatar || '/src/assets/user.svg'"
                  alt="用户头像"
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

    <!-- 工作区主内容 -->
    <div class="workspace-main">
    <!-- 左侧边栏 -->
    <div class="sidebar">
      <!-- 应用中心按钮 -->
      <div class="create-section">
        <button @click="goToHomepage" class="create-btn-native">
          <div class="btn-content">
            <span class="icon">
              <img src="../../assets/application-center.svg" width="30px" height="30px" />
            </span>
            <span>应用中心</span>
          </div>
        </button>
      </div>

      <!-- 会话列表 -->
      <div class="session-list">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <div class="loading-icon">⏳</div>
          <div class="loading-text">正在加载会话列表...</div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="sessions.length === 0" class="empty-state">
          <img src="../../assets/workspace-session.svg" alt="暂无会话" class="empty-icon-img" />
          <div class="empty-text">暂无会话记录</div>
        </div>

        <!-- 会话卡片 -->
        <div
          v-for="session in sessions"
          :key="session.sessionId"
          :class="['session-card', { active: selectedSession === session.sessionId }]"
          @click="selectSession(session.sessionId)"
        >
          <div class="session-icon">
            <img src="../../assets/workspace-session.svg" width="30px" height="30px" />
          </div>
          <div class="session-info">
            <div class="session-title">{{ session.title }}</div>
            <div class="session-time">{{ formatTime(session.createTime) }}</div>
          </div>
          <button
            class="delete-btn"
            @click="deleteSession(session.sessionId, $event)"
            title="删除会话"
          >
            ×
          </button>
        </div>
      </div>
    </div>

    <!-- 右侧内容区域 -->
    <div class="content">
      <router-view />
    </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.workspace-container {
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&family=Zhi+Mang+Xing&family=Ma+Shan+Zheng&display=swap');
}
.workspace-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #fff9f2;
}

.workspace-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64px;
  background: #ffffff;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(255, 159, 67, 0.1);
  position: relative;
  z-index: 3000;

  .nav-left {
    display: flex;
    align-items: center;

    .logo-section {
      display: flex;
      align-items: center;
      gap: 12px;

      .logo {
        width: 40px;
        height: 40px;
          display: block;
          object-fit: contain;
        filter: drop-shadow(0 0 5px rgba(255, 159, 67, 0.4));
      }
    }

    .nav-links {
      display: flex;
      align-items: center;
      margin-left: 8px;
      gap: 10px;

        .brand-logo-img {
          height: 56px;
          width: auto;
          display: block;
          filter: drop-shadow(0 2px 6px rgba(255, 159, 67, 0.3));
          user-select: none;
        }

      .nav-link {
        background: #fffbf7;
        color: #5c3d2e;
        border: 1px solid #ffe0b2;
        height: 40px;
        padding: 0 14px;
        border-radius: 14px;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.4px;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        position: relative;

        &:hover {
          background: #fff3e0;
          transform: translateY(-1px);
          box-shadow: 0 8px 18px rgba(255, 159, 67, 0.1);
          border-color: #ff9f43;
        }

        .icon {
          width: 20px;
          height: 20px;
          display: inline-flex;
          align-items: center;
          justify-content: center;

          img {
            width: 20px;
            height: 20px;
          }
        }
      }

      .workspace-link {
        background: linear-gradient(135deg, rgba(255, 159, 67, 0.1), rgba(255, 107, 107, 0.1));
        border-color: rgba(255, 159, 67, 0.2);

        &:hover {
          background: linear-gradient(135deg, rgba(255, 159, 67, 0.2), rgba(255, 107, 107, 0.2));
        }

        &.active {
          background: #fff3e0;
          border-color: #ff9f43;
          color: #5c3d2e;
          box-shadow: inset 0 0 0 1px rgba(255, 159, 67, 0.2);

          &::after {
            content: '';
            position: absolute;
            left: 12px;
            right: 12px;
            bottom: -5px;
            height: 2px;
            border-radius: 2px;
            background: #ff9f43;
          }
        }
      }
    }
  }

  .nav-right {
    .user-info {
      .user-avatar-wrapper {
        display: flex;
        align-items: center;
        padding: 4px;
        border-radius: 50%;
        background: rgba(255, 159, 67, 0.1);
        backdrop-filter: blur(10px);
        cursor: pointer;
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 159, 67, 0.2);

        &:hover {
          background: rgba(255, 159, 67, 0.2);
          transform: translateY(-2px);
          box-shadow: 0 8px 16px rgba(255, 159, 67, 0.15);
          border-color: #ff9f43;
        }

        .user-avatar {
          img {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid #ff9f43;
            object-fit: cover;
            box-shadow: 0 4px 10px rgba(255, 159, 67, 0.2);
            transition: all 0.3s ease;

            &:hover {
              border-color: #ff8c1a;
              transform: scale(1.05);
            }
          }
        }
      }
    }
  }
}

.workspace-main {
  display: flex;
  flex: 1;
  height: calc(100vh - 64px);
  background-color: #fff9f2;

  .sidebar {
    height: 100%;
    width: 280px;
    background-color: #ffffff;
    border-right: 1px solid #ffe0b2;
    display: flex;
    flex-direction: column;
    box-shadow: 2px 0 8px rgba(255, 159, 67, 0.05);

    .create-section {
      padding: 20px 16px;

      .create-btn-native {
        width: 100%;
        height: 48px;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
        background: white;
        color: #ff9f43;
        border: 2px solid #ff9f43;
        cursor: pointer;
        font-size: 15px;
        font-family: 'PingFang SC', 'Microsoft YaHei UI', 'Source Han Sans CN', 'Noto Sans CJK SC', sans-serif;
        letter-spacing: 1px;

        &:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(255, 159, 67, 0.3);
          background: #fff3e0;
        }

        &:active {
          transform: translateY(0);
        }

        .btn-content {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;

          .icon {
            font-size: 20px;
          }
        }
      }
    }

    .session-list {
      flex: 1;
      padding: 8px;
      overflow-y: auto;

      .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: #ff9f43;

        .loading-icon {
          font-size: 48px;
          margin-bottom: 16px;
          animation: spin 1s linear infinite;
        }

        .loading-text {
          font-size: 14px;
          color: #8d6e63;
        }
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 200px;
        color: #9ca3af;

        .empty-icon {
          font-size: 48px;
          margin-bottom: 16px;
        }

        .empty-icon-img {
          width: 60px;
          height: 60px;
          margin-bottom: 16px;
          object-fit: contain;
          opacity: 0.9;
        }

        .empty-text {
          font-size: 16px;
          font-weight: 600;
          color: #6b7280;
          letter-spacing: 0.2px;
          margin-bottom: 8px;
        }

        .empty-hint {
          font-size: 12px;
          color: #d1d5db;
        }
      }

      .session-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
        border: 1px solid transparent;
        background-color: #fffbf7;

        &:hover {
          background-color: #fff3e0;
          border-color: #ffbd69;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(255, 159, 67, 0.1);
        }

        &.active {
          background-color: #fff3e0;
          border-color: #ff9f43;
          box-shadow: 0 4px 12px rgba(255, 159, 67, 0.15);

          .session-title {
            color: #ff9f43;
            font-weight: 600;
          }
        }

        .session-icon {
          flex-shrink: 0;
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: #fffbf7;
          border-radius: 10px;
          border: 1px solid #ffe0b2;
          
          img {
            filter: sepia(100%) saturate(300%) hue-rotate(350deg) brightness(80%);
          }
        }

        .session-info {
          flex: 1;
          min-width: 0;

          .session-title {
            font-size: 14px;
            color: #5c3d2e;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-bottom: 4px;
          }

          .session-time {
            font-size: 11px;
            color: #ffbd69;
          }
        }

        .delete-btn {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(255, 255, 255, 0.8);
          border: 1px solid #ffe0b2;
          border-radius: 6px;
          color: #8d6e63;
          font-size: 16px;
          opacity: 0;
          transition: all 0.2s ease;

          &:hover {
            background-color: #fff3e0;
            color: #ff6b6b;
            border-color: #ff6b6b;
          }
        }

        &:hover .delete-btn {
          opacity: 1;
        }
      }
    }
  }

  .content {
    flex: 1;
    overflow: hidden;
    background-color: #fff9f2;
  }
}

// 动画
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// 下拉菜单样式
:deep(.el-dropdown-menu) {
  border: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
  
  .el-dropdown-menu__item {
    padding: 12px 16px;
    font-size: 14px;
    
    &:hover {
      background-color: #fff3e0;
      color: #ff9f43;
    }
    
    .el-icon {
      margin-right: 8px;
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .workspace-nav {
    .nav-left {
      .logo-section {
        .brand-name {
          display: none;
        }
      }
    }
  }

  .workspace-main {
    .sidebar {
      width: 240px;
    }

    .content {
      margin: 0;
    }
  }
}

@media (max-width: 480px) {
  .workspace-nav {
    padding: 0 12px;
  }

  .workspace-main {
    flex-direction: column;

    .sidebar {
      width: 100%;
      height: auto;
      max-height: 300px;
    }

    .content {
      flex: 1;
      margin: 0;
    }
  }
}
</style>
