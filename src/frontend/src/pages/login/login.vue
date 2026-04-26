<template>
  <div class="login-container">
    <!-- 背景装饰元素 -->
    <div class="bg-decoration">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <div class="login-card-inner">
        <!-- Logo和标题 -->
        <div class="header">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <img src="../../assets/agentchat.svg" alt="饺子 Agent" class="logo-img" />
            </div>
            <h1 class="logo-text">饺子 Agent</h1>
          </div>
          <p class="subtitle">开启您的智能协作新纪元</p>
        </div>

        <!-- 登录表单 -->
        <div class="login-form">
          <div class="form-item">
            <div class="input-wrapper">
              <el-input
                v-model="loginForm.username"
                placeholder="用户名 / 账号"
                size="large"
                class="custom-input"
                @keyup.enter="handleLogin"
              >
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </div>
          </div>

          <div class="form-item">
            <div class="input-wrapper">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="密码"
                size="large"
                class="custom-input"
                show-password
                @keyup.enter="handleLogin"
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </div>
          </div>

          <div class="form-options">
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <a href="#" class="forgot-pwd">忘记密码？</a>
          </div>

          <el-button
            type="primary"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            进入平台
          </el-button>

          <div class="register-footer">
            <span>还没有账号？</span>
            <el-button link type="primary" @click="goToRegister">立即注册</el-button>
          </div>
        </div>

        <!-- 底部版本信息 -->
        <div class="footer">
          <span class="version">v2.4.0</span>
          
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { loginAPI, getUserInfoAPI } from '../../apis/auth'
import { useUserStore } from '../../store/user'

const router = useRouter()
const userStore = useUserStore()

const loginForm = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const rememberMe = ref(false)

const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  try {
    loading.value = true
    const response = await loginAPI(loginForm)
    const responseData = response.data
    if (responseData.status_code === 200) {
      ElMessage.success('登录成功')
      const userData = responseData.data || {}
      if (userData.access_token && userData.user_id) {
        userStore.setUserInfo(userData.access_token, {
          id: userData.user_id,
          username: loginForm.username
        })
        try {
          const userInfoResponse = await getUserInfoAPI(userData.user_id)
          const userInfoData = userInfoResponse.data
          if (userInfoData.status_code === 200) {
            const completeUserData = userInfoData.data || {}
            userStore.updateUserInfo({
              avatar: completeUserData.user_avatar || completeUserData.avatar,
              description: completeUserData.user_description || completeUserData.description
            })
          }
        } catch (error) {
          console.error('获取用户详细信息失败:', error)
        }
      }
      router.push('/')
    } else {
      ElMessage.error(responseData.status_message || '登录失败')
    }
  } catch (error: any) {
    console.error('登录错误:', error)
    if (error.response?.data?.message) {
      ElMessage.error(error.response.data.status_message)
    } else if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    } else {
      ElMessage.error('登录失败，请检查网络连接')
    }
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  router.push('/register')
}
</script>

<style lang="scss" scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fff9f2;
  position: relative;
  overflow: hidden;
  font-family: 'PingFang SC', 'Helvetica Neue', Arial, sans-serif;
}

.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;

  .blob {
    position: absolute;
    filter: blur(80px);
    border-radius: 50%;
    opacity: 0.5;
    z-index: 1;
  }

  .blob-1 {
    width: 400px;
    height: 400px;
    background: #ffe0b2;
    top: -100px;
    right: -100px;
    animation: move1 20s infinite alternate;
  }

  .blob-2 {
    width: 500px;
    height: 500px;
    background: #ffccbc;
    bottom: -150px;
    left: -100px;
    animation: move2 25s infinite alternate;
  }

  .blob-3 {
    width: 300px;
    height: 300px;
    background: #fff3e0;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }
}

@keyframes move1 {
  from { transform: translate(0, 0); }
  to { transform: translate(-100px, 100px); }
}

@keyframes move2 {
  from { transform: translate(0, 0); }
  to { transform: translate(150px, -100px); }
}

.login-card {
  width: 100%;
  max-width: 440px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 224, 178, 0.5);
  border-radius: 24px;
  padding: 40px;
  box-shadow: 0 20px 40px rgba(255, 159, 67, 0.1);
  position: relative;
  z-index: 2;
  margin: 20px;
}

.header {
  text-align: center;
  margin-bottom: 40px;

  .logo-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .logo-icon {
      width: 64px;
      height: 64px;
      background: #fff;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 16px rgba(255, 159, 67, 0.2);
      
      .logo-img {
        width: 40px;
        height: 40px;
        filter: drop-shadow(0 2px 4px rgba(255, 159, 67, 0.3));
      }
    }

    .logo-text {
      font-size: 28px;
      font-weight: 800;
      background: linear-gradient(135deg, #ff9f43 0%, #ff6b6b 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin: 0;
      letter-spacing: 1px;
    }
  }

  .subtitle {
    font-size: 15px;
    color: #8d6e63;
    margin: 0;
  }
}

.login-form {
  .form-item {
    margin-bottom: 20px;
  }

  .custom-input {
    :deep(.el-input__wrapper) {
      background-color: #fff;
      border: 1px solid #ffe0b2;
      box-shadow: none !important;
      border-radius: 12px;
      padding: 4px 12px;
      transition: all 0.3s ease;

      &:hover {
        border-color: #ff9f43;
      }

      &.is-focus {
        border-color: #ff9f43;
        background-color: #fff;
        box-shadow: 0 0 0 4px rgba(255, 159, 67, 0.1) !important;
      }
    }

    :deep(.el-input__inner) {
      height: 48px;
      font-size: 15px;
      color: #5c3d2e;

      &::placeholder {
        color: #ffbd69;
      }
    }

    :deep(.el-input__prefix-inner) {
      color: #ff9f43;
      font-size: 18px;
    }
  }

  .form-options {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;

    :deep(.el-checkbox__label) {
      color: #8d6e63;
      font-size: 14px;
    }

    :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
      background-color: #ff9f43;
      border-color: #ff9f43;
    }

    .forgot-pwd {
      font-size: 14px;
      color: #ff9f43;
      text-decoration: none;
      transition: color 0.3s;

      &:hover {
        color: #ff8c1a;
      }
    }
  }

  .login-btn {
    width: 100%;
    height: 52px;
    border-radius: 12px;
    background: linear-gradient(135deg, #ff9f43 0%, #ff8c1a 100%);
    border: none;
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 20px;
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 20px rgba(255, 159, 67, 0.3);
      opacity: 0.95;
    }

    &:active {
      transform: translateY(0);
    }
  }

  .register-footer {
    text-align: center;
    font-size: 14px;
    color: #8d6e63;

    :deep(.el-button--link) {
      color: #ff9f43;
      font-weight: 600;
      padding: 0 4px;
      
      &:hover {
        color: #ff8c1a;
      }
    }
  }
}

.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid #ffe0b2;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .version {
    font-size: 12px;
    color: #ffbd69;
    background: #fff3e0;
    padding: 2px 8px;
    border-radius: 6px;
  }

  .links {
    display: flex;
    gap: 12px;

    a {
      img {
        width: 20px;
        height: 20px;
        opacity: 0.6;
        transition: opacity 0.3s;
        filter: sepia(100%) saturate(300%) hue-rotate(350deg) brightness(80%);

        &:hover {
          opacity: 1;
        }
      }
    }
  }
}
</style>
