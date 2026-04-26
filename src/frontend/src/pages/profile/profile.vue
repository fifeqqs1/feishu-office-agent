<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Edit, Upload, Check, Close } from '@element-plus/icons-vue'
import { useUserStore } from '../../store/user'
import { updateUserInfoAPI, getUserIconsAPI, getUserInfoAPI } from '../../apis/auth'

const userStore = useUserStore()

// 表单数据
const formData = ref({
  user_avatar: '',
  user_description: '该用户很懒，没有留下一片云彩'
})

// 测试按钮点击
const testButtonClick = () => {
  console.log('按钮被点击了！');
  alert('按钮被点击了！');
  confirmAvatarSelection();
}

// 页面状态
const loading = ref(false)
const iconsLoading = ref(false)
const editingDescription = ref(false)
const showAvatarDialog = ref(false)
const pageLoading = ref(true)
const uploading = ref(false)

// 上传请求头
const uploadHeaders = computed(() => ({
  'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
}))

// 头像相关
const availableIcons = ref<string[]>([])
const selectedAvatar = ref('')
const uploadRef = ref()

// 初始化数据
onMounted(async () => {
  await loadUserInfo()
  await loadAvailableIcons()
  pageLoading.value = false
})

// 获取用户信息
const loadUserInfo = async () => {
  try {
    const userId = userStore.userInfo?.id
    
    if (userId) {
      const response = await getUserInfoAPI(userId)
      
      if (response.data.status_code === 200) {
        const userInfo = response.data.data
        
        // 更新本地存储的用户信息，适配数据库字段
        const updatedInfo = {
          id: userInfo.user_id || userInfo.id,
          username: userInfo.user_name || userInfo.username,
          avatar: userInfo.user_avatar || userInfo.avatar,
          description: userInfo.user_description || userInfo.description
        }
        userStore.updateUserInfo(updatedInfo)
        
        // 更新表单数据
        formData.value = {
          user_avatar: userInfo.user_avatar || userInfo.avatar || '/src/assets/user.svg',
          user_description: userInfo.user_description || userInfo.description || '该用户很懒，没有留下一片云彩'
        }
        selectedAvatar.value = formData.value.user_avatar
      }
    } else {
      // 如果没有用户ID，使用本地存储的信息
      formData.value = {
        user_avatar: userStore.userInfo?.avatar || '/src/assets/user.svg',
        user_description: userStore.userInfo?.description || '该用户很懒，没有留下一片云彩'
      }
      selectedAvatar.value = formData.value.user_avatar
    }
  } catch (error) {
    console.error('获取用户信息失败:', error)
    // 使用本地存储的信息作为备选
    formData.value = {
      user_avatar: userStore.userInfo?.avatar || '/src/assets/user.svg',
      user_description: userStore.userInfo?.description || '该用户很懒，没有留下一片云彩'
    }
    selectedAvatar.value = formData.value.user_avatar
  }
}

// 获取可选头像
const loadAvailableIcons = async () => {
  iconsLoading.value = true
  try {
    const response = await getUserIconsAPI()
    // 修复：后端返回的是code，不是code
    if (response.data.status_code === 200) {
      availableIcons.value = response.data.data
    }
  } catch (error) {
    console.error('获取头像列表失败:', error)
    ElMessage.error('获取头像列表失败')
  } finally {
    iconsLoading.value = false
  }
}

// 选择头像
const selectAvatar = (avatarUrl: string) => {
  selectedAvatar.value = avatarUrl
}

// 确认选择头像
const confirmAvatarSelection = async () => {
  const userId = userStore.userInfo?.id
  if (!userId) {
    ElMessage.error('用户ID不存在')
    return
  }
  
  // 更新表单数据
  formData.value.user_avatar = selectedAvatar.value
  
  try {
    // 直接保存头像更改到服务器
    const response = await updateUserInfoAPI(
      userId,
      selectedAvatar.value,
      formData.value.user_description
    )
    
    if (response.data.status_code === 200) {
      // 更新本地用户信息
      userStore.updateUserInfo({
        avatar: selectedAvatar.value
      })
      
      showAvatarDialog.value = false
      ElMessage.success('头像更新成功')
    } else {
      ElMessage.error(response.data.status_message || '头像更新失败')
    }
  } catch (error) {
    console.error('头像更新失败:', error)
    ElMessage.error('头像更新失败')
  }
}

// 上传自定义头像
const handleUploadSuccess = async (response: any) => {
  // 后端直接返回图片链接字符串，格式为: data = "http........."
  const imageUrl = typeof response === 'string' ? response : response.data
  
  if (imageUrl) {
    // 只更新选中的头像，不立即保存到服务器
    selectedAvatar.value = imageUrl;
    uploading.value = false;
    ElMessage.success('头像上传成功，请点击"确定选择"保存');
  } else {
    ElMessage.error('上传失败，未获取到图片链接');
    uploading.value = false;
  }
}

// 上传前验证
const beforeUpload = (file: File) => {
  const isJPGOrPNG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isJPGOrPNG) {
    ElMessage.error('只能上传 JPG/PNG 格式的图片!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }
  
  uploading.value = true
  return true
}

// 上传失败处理
const handleUploadError = (error: any) => {
  console.error('上传失败:', error)
  ElMessage.error('头像上传失败，请重试')
  uploading.value = false
}

// 保存用户信息
const saveUserInfo = async () => {
  loading.value = true
  try {
    const userId = userStore.userInfo?.id
    if (!userId) {
      ElMessage.error('用户ID不存在')
      return
    }
    
    const response = await updateUserInfoAPI(
      userId,
      formData.value.user_avatar,
      formData.value.user_description
    )
    
    if (response.data.status_code === 200) {
      // 更新本地用户信息，映射字段名
      userStore.updateUserInfo({
        avatar: formData.value.user_avatar,
        description: formData.value.user_description
      })
      
      ElMessage.success('保存成功')
      editingDescription.value = false
    } else {
      ElMessage.error(response.data.status_message || '保存失败')
    }
  } catch (error) {
    console.error('保存用户信息失败:', error)
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}

// 编辑描述
const startEditDescription = () => {
  editingDescription.value = true
}

const cancelEditDescription = () => {
  editingDescription.value = false
  // 恢复原始值
  formData.value.user_description = userStore.userInfo?.description || '该用户很懒，没有留下一片云彩'
}

// 处理图片加载错误
const handleImageError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = '/src/assets/user.svg' // 设置默认头像
}

// 处理自定义上传
const handleCustomUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;
  
  const file = input.files[0];
  
  // 验证文件类型
  const isJPGOrPNG = file.type === 'image/jpeg' || file.type === 'image/png';
  const isLt2M = file.size / 1024 / 1024 < 2;

  if (!isJPGOrPNG) {
    ElMessage.error('只能上传 JPG/PNG 格式的图片!');
    return;
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!');
    return;
  }
  
  uploading.value = true;
  
  try {
    // 创建表单数据
    const formData = new FormData();
    formData.append('file', file);
    
    // 发送请求
    const response = await fetch('/api/v1/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
      },
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('上传失败');
    }
    
    const result = await response.json();
    
    // 处理响应
    handleUploadSuccess(result);
  } catch (error) {
    console.error('上传失败:', error);
    ElMessage.error('头像上传失败，请重试');
    uploading.value = false;
  }
};
</script>

<template>
  <div class="profile-page" v-loading="pageLoading">
    <div class="profile-header">
      <div>
        <h2>个人资料</h2>
        <p>管理您的个人信息和偏好设置</p>
      </div>
      <el-button type="primary" @click="loadUserInfo" :loading="pageLoading">
        刷新信息
      </el-button>
    </div>

    <div class="profile-content" v-if="!pageLoading">
      <div class="profile-card">
        <!-- 用户头像区域 -->
        <div class="avatar-section">
          <div class="avatar-container">
            <div class="avatar-wrapper">
              <img 
                :src="formData.user_avatar" 
                alt="用户头像"
                class="user-avatar"
                @error="handleImageError"
              />
              <div class="avatar-overlay" @click="showAvatarDialog = true">
                <el-icon><Edit /></el-icon>
              </div>
            </div>
          </div>
          
          <div class="user-basic-info">
            <h3>{{ userStore.userInfo?.nickname || userStore.userInfo?.username || '用户' }}</h3>
            <p class="user-id">ID: {{ userStore.userInfo?.id || '未知' }}</p>
          </div>
        </div>

        <!-- 用户描述区域 -->
        <div class="description-section">
          <div class="section-header">
            <h4>个人描述</h4>
            <el-button 
              v-if="!editingDescription"
              type="primary" 
              size="small" 
              :icon="Edit"
              @click="startEditDescription"
            >
              编辑
            </el-button>
          </div>
          
          <div v-if="!editingDescription" class="description-display">
            <p>{{ formData.user_description }}</p>
          </div>
          
          <div v-else class="description-edit">
            <el-input
              v-model="formData.user_description"
              type="textarea"
              :rows="4"
              placeholder="请输入个人描述"
              maxlength="200"
              show-word-limit
            />
            <div class="edit-actions">
              <el-button size="small" @click="cancelEditDescription">
                <el-icon><Close /></el-icon>
                取消
              </el-button>
              <el-button 
                type="primary" 
                size="small" 
                :loading="loading"
                @click="saveUserInfo"
              >
                <el-icon><Check /></el-icon>
                保存
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 头像选择对话框 -->
    <el-dialog
      v-model="showAvatarDialog"
      title="选择头像"
      width="600px"
      :close-on-click-modal="false"
      append-to-body
      class="orange-dialog"
    >
      <div class="avatar-selection">
        <!-- 当前选中头像 -->
        <div class="current-selection">
          <h4>当前选择：</h4>
          <div class="selected-avatar">
            <img :src="selectedAvatar" alt="选中的头像" />
          </div>
        </div>

        <div class="avatar-content-main">
          <!-- 预设头像列表 -->
          <div class="preset-avatars">
            <h4>选择预设头像：</h4>
            <div class="avatar-grid">
              <div
                v-for="(icon, index) in availableIcons"
                :key="index"
                class="avatar-option"
                :class="{ active: selectedAvatar === icon }"
                @click="selectAvatar(icon)"
              >
                <img :src="icon" alt="头像选项" />
              </div>
            </div>
          </div>

          <!-- 上传自定义头像 -->
          <div class="upload-section">
            <h4>上传自定义头像：</h4>
            <div class="upload-area-custom">
              <el-upload
                ref="uploadRef"
                action="/api/v1/upload"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleUploadSuccess"
                :before-upload="beforeUpload"
                :on-error="handleUploadError"
                accept="image/*"
                :disabled="uploading"
              >
                <el-button type="primary" :icon="Upload" :loading="uploading" class="orange-btn">
                  {{ uploading ? '上传中...' : '点击上传头像' }}
                </el-button>
              </el-upload>
              <p class="upload-tip">支持 JPG、PNG 格式，文件大小不超过 2MB</p>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showAvatarDialog = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="testButtonClick"
            :disabled="!selectedAvatar"
            class="orange-btn"
          >
            确定选择
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.profile-page {
  padding: 24px;
  background-color: #fff9f2;
  min-height: calc(100vh - 104px); // Adjusted for main layout padding

  .profile-header {
    margin-bottom: 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0 0 8px 0;
      font-size: 28px;
      font-weight: 600;
      color: #5c3d2e;
    }

    p {
      margin: 0;
      color: #8d6e63;
      font-size: 16px;
    }
  }

  .profile-content {
    max-width: 800px;

    .profile-card {
      background: white;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 4px 20px rgba(255, 159, 67, 0.1);
      border: 1px solid #ffe0b2;

      .avatar-section {
        display: flex;
        align-items: center;
        margin-bottom: 32px;
        padding-bottom: 24px;
        border-bottom: 1px solid #ffe0b2;

        .avatar-container {
          margin-right: 24px;

          .avatar-wrapper {
            position: relative;
            width: 100px;
            height: 100px;
            cursor: pointer;

            .user-avatar {
              width: 100%;
              height: 100%;
              border-radius: 50%;
              object-fit: cover;
              border: 4px solid #ff9f43;
              box-shadow: 0 4px 12px rgba(255, 159, 67, 0.2);
            }

            .avatar-overlay {
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              bottom: 0;
              background: rgba(92, 61, 46, 0.4);
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              opacity: 0;
              transition: opacity 0.3s ease;
              color: white;
              font-size: 24px;

              &:hover {
                opacity: 1;
              }
            }
          }
        }

        .user-basic-info {
          h3 {
            margin: 0 0 8px 0;
            font-size: 24px;
            font-weight: 600;
            color: #5c3d2e;
          }

          .user-id {
            margin: 0;
            color: #8d6e63;
            font-size: 14px;
            background: #fff3e0;
            padding: 2px 8px;
            border-radius: 4px;
            display: inline-block;
          }
        }
      }

      .description-section {
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;

          h4 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: #5c3d2e;
          }
        }

        .description-display {
          p {
            margin: 0;
            font-size: 16px;
            line-height: 1.6;
            color: #5c3d2e;
            background: #fffbf7;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #ffe0b2;
          }
        }

        .description-edit {
          .edit-actions {
            margin-top: 12px;
            display: flex;
            justify-content: flex-end;
            gap: 8px;
          }
        }
      }
    }
  }
}

// 通用按钮和输入框覆盖
.orange-btn {
  background-color: #ff9f43 !important;
  border-color: #ff9f43 !important;
  color: #fff !important;

  &:hover {
    background-color: #ff8c1a !important;
    border-color: #ff8c1a !important;
  }
}

:deep(.el-button--primary) {
  background-color: #ff9f43;
  border-color: #ff9f43;
  
  &:hover {
    background-color: #ff8c1a;
    border-color: #ff8c1a;
  }
}

:deep(.el-textarea__inner) {
  border-radius: 12px;
  &:focus {
    border-color: #ff9f43;
    box-shadow: 0 0 0 2px rgba(255, 159, 67, 0.2);
  }
}

// 对话框样式
:deep(.orange-dialog) {
  border-radius: 16px;
  overflow: hidden;
  
  .el-dialog__header {
    margin-right: 0;
    padding: 20px;
    background-color: #fffbf7;
    border-bottom: 1px solid #ffe0b2;
    
    .el-dialog__title {
      color: #5c3d2e;
      font-weight: 600;
    }
  }
  
  .el-dialog__body {
    padding: 24px;
  }
  
  .el-dialog__footer {
    padding: 16px 20px;
    border-top: 1px solid #ffe0b2;
    background-color: #fffbf7;
  }
}

.avatar-selection {
  display: flex;
  flex-direction: column;
  gap: 24px;

  .current-selection {
    text-align: center;
    padding: 16px;
    background: #fffbf7;
    border-radius: 12px;
    border: 1px solid #ffe0b2;

    h4 {
      margin-bottom: 12px;
      font-size: 16px;
      color: #5c3d2e;
    }

    .selected-avatar {
      img {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid #ff9f43;
        box-shadow: 0 4px 12px rgba(255, 159, 67, 0.2);
      }
    }
  }

  .avatar-content-main {
    display: flex;
    gap: 24px;
    
    .preset-avatars {
      flex: 1;
      
      h4 {
        margin-bottom: 16px;
        font-size: 16px;
        color: #5c3d2e;
      }

      .avatar-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
        gap: 12px;
        max-height: 240px;
        overflow-y: auto;
        padding-right: 8px;

        &::-webkit-scrollbar {
          width: 6px;
        }
        &::-webkit-scrollbar-thumb {
          background: #ffe0b2;
          border-radius: 3px;
        }

        .avatar-option {
          width: 60px;
          height: 60px;
          cursor: pointer;
          border: 2px solid transparent;
          border-radius: 50%;
          overflow: hidden;
          transition: all 0.2s ease;

          &:hover:not(.active) {
            border-color: #ff9f43;
            transform: scale(1.05);
          }

          &.active {
            border-color: #ff9f43;
            box-shadow: 0 0 0 2px rgba(255, 159, 67, 0.3);
          }

          img {
            width: 100%;
            height: 100%;
            object-fit: cover;
          }
        }
      }
    }

    .upload-section {
      width: 200px;
      
      h4 {
        margin-bottom: 16px;
        font-size: 16px;
        color: #5c3d2e;
      }

      .upload-area-custom {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        padding: 20px;
        background: #fffbf7;
        border-radius: 12px;
        border: 1px dashed #ffe0b2;

        .upload-tip {
          font-size: 12px;
          color: #8d6e63;
          text-align: center;
          line-height: 1.4;
        }
      }
    }
  }
}
</style> 