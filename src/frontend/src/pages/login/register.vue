<template>
  <div class="register-container">
    <!-- 背景装饰元素 -->
    <div class="bg-decoration">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <!-- 注册卡片 -->
    <div class="register-card">
      <div class="register-card-inner">
        <!-- Logo和标题 -->
        <div class="header">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <img src="../../assets/agentchat.svg" alt="饺子 Agent" class="logo-img" />
            </div>
            <h1 class="logo-text">饺子 Agent</h1>
          </div>
          <p class="subtitle">创建您的账户，开启智能协作之旅</p>
        </div>

        <!-- 注册表单 -->
        <div class="register-form">
          <div class="form-item">
            <el-input
              v-model="registerForm.user_name"
              placeholder="用户名"
              size="large"
              class="custom-input"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="form-item">
            <el-input
              v-model="registerForm.user_email"
              placeholder="邮箱地址 (可选)"
              size="large"
              class="custom-input"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Message /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="form-item">
            <el-input
              v-model="registerForm.user_password"
              type="password"
              placeholder="设置密码"
              size="large"
              class="custom-input"
              show-password
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="form-item">
            <el-input
              v-model="confirmPassword"
              type="password"
              placeholder="确认密码"
              size="large"
              class="custom-input"
              show-password
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Checked /></el-icon>
              </template>
            </el-input>
          </div>

          <el-button
            type="primary"
            class="register-btn"
            :loading="loading"
            @click="handleRegister"
          >
            立即注册
          </el-button>

          <div class="login-footer">
            <span>已有账号？</span>
            <el-button link type="primary" @click="goToLogin">去登录</el-button>
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
import { User, Lock, Message, Checked } from '@element-plus/icons-vue'
import { registerAPI } from '../../apis/auth'
import type { RegisterForm } from '../../apis/auth'

const router = useRouter()

const registerForm = reactive<RegisterForm>({
  user_name: '',
  user_email: '',
  user_password: ''
})

const confirmPassword = ref('')
const loading = ref(false)

const validateForm = () => {
  if (!registerForm.user_name) {
    ElMessage.warning('请输入用户名')
    return false
  }

  if (registerForm.user_name.length > 20) {
    ElMessage.warning('用户名长度不应该超过20个字符')
    return false
  }

  if (!registerForm.user_password) {
    ElMessage.warning('请输入密码')
    return false
  }

  if (registerForm.user_password.length < 6) {
    ElMessage.warning('密码长度至少6个字符')
    return false
  }

  if (registerForm.user_password !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return false
  }

  if (registerForm.user_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerForm.user_email)) {
    ElMessage.warning('请输入有效的邮箱地址')
    return false
  }

  return true
}

const handleRegister = async () => {
  if (!validateForm()) {
    return
  }

  try {
    loading.value = true
    const response = await registerAPI(registerForm)

    if (response.data.status_code === 200) {
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } else {
      ElMessage.error(response.data.status_message || '注册失败')
    }
  } catch (error: any) {
    console.error('注册错误:', error)
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    } else {
      ElMessage.error('注册失败，请检查网络连接')
    }
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.register-container {
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

.register-card {
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
  margin-bottom: 30px;

  .logo-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;

    .logo-icon {
      width: 56px;
      height: 56px;
      background: #fff;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 16px rgba(255, 159, 67, 0.15);

      .logo-img {
        width: 32px;
        height: 32px;
        filter: drop-shadow(0 2px 4px rgba(255, 159, 67, 0.3));
      }
    }

    .logo-text {
      font-size: 26px;
      font-weight: 800;
      background: linear-gradient(135deg, #ff9f43 0%, #ff6b6b 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin: 0;
      letter-spacing: 1px;
    }
  }

  .subtitle {
    font-size: 14px;
    color: #8d6e63;
    margin: 0;
  }
}

.register-form {
  .form-item {
    margin-bottom: 16px;
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
      height: 44px;
      font-size: 14px;
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

  .register-btn {
    width: 100%;
    height: 48px;
    border-radius: 12px;
    background: linear-gradient(135deg, #ff9f43 0%, #ff8c1a 100%);
    border: none;
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    margin-top: 10px;
    margin-bottom: 16px;
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

  .login-footer {
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
  margin-top: 30px;
  padding-top: 16px;
  border-top: 1px solid #ffe0b2;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .version {
    font-size: 11px;
    color: #ffbd69;
    background: #fff3e0;
    padding: 2px 6px;
    border-radius: 6px;
  }

  .links {
    display: flex;
    gap: 12px;

    a {
      img {
        width: 18px;
        height: 18px;
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

