/**
 * Live2D模型管理器
 * 处理Live2D模型的加载、渲染和交互
 */
export default class Live2dModelManager {
  constructor(vueComponent) {
    this.vue = vueComponent; // 保存Vue组件引用以访问其属性和方法
    
    // 从Vue组件复制必要的状态
    this.selectedModel = vueComponent.selectedModel;
    this.eyesFollow = vueComponent.eyesFollow;
    this.modelLoaded = false;
    this.live2dModel = null;
    
    // 模型尺寸相关参数
    this.modelSize = { width: 300, height: 500 };
    this.canvasSize = { width: 600, height: 600 };
    this.scaleFactor = 1.0;
    
    // 口型相关参数
    this.mouthOpenValue = 0;
    this.mouthUpdateInterval = null;
    this.mouthOpenParamName = null;
    this.usingBuiltInSpeech = false;
    
    // 音频相关
    this.audioContext = null;
    this.audioSource = null;
    this.audioAnalyser = null;
    this.frequencyData = null;
    
    // 动作和表情列表
    this.motions = [];
    this.expressions = [];
    this.app = null; // PIXI应用实例
  }
  
  /**
   * 获取可用的模型列表
   * @returns {string[]} 模型名称数组
   */
  getAvailableModels() {
    // 返回默认模型列表 (在实际应用中可以从服务器获取或扫描目录)
    return ['Hiyori', 'March 7th', 'MuraSame'];
  }
  
  /**
   * 初始化Live2D环境和模型
   */
  async initLive2D() {
    console.log('初始化Live2D...');
    if (!window.PIXI) {
      this.vue.loadingError = 'PIXI未加载，请检查脚本';
      return;
    }
    
    const PIXI = window.PIXI;
    if (!PIXI.live2d) {
      this.vue.loadingError = 'live2d插件未加载，请检查脚本';
      return;
    }
    
    try {
      // 获取canvas元素
      const canvas = document.getElementById("canvas");
      if (!canvas) {
        console.error('Canvas元素未找到');
        this.vue.loadingError = 'Canvas元素未找到';
        return;
      }
      
      // 设置初始canvas尺寸
      const initialWidth = 600;
      const initialHeight = 1200;
      
      canvas.width = initialWidth;
      canvas.height = initialHeight;
      
      console.log('初始Canvas尺寸设置为:', initialWidth, 'x', initialHeight);
      
      // 创建PIXI应用，确保透明背景
      this.app = new PIXI.Application({
        view: canvas,
        width: initialWidth,
        height: initialHeight,
        transparent: true,        // 确保透明
        autoStart: true,
        antialias: true,
        backgroundColor: 0x00000000,  // 完全透明
        backgroundAlpha: 0,
        clearBeforeRender: true,  // 每次渲染前清除
      });
      
      // 确保舞台背景透明
      this.app.stage.alpha = 1;
      this.app.stage.interactive = true;
      
      // 应用CSS确保透明
      canvas.style.backgroundColor = 'transparent';
      
      // 使用绝对路径来加载模型
      const modelPath = `/src/assets/models/${this.vue.selectedModel}/${this.vue.selectedModel}.model3.json`;
      console.log('加载模型路径:', modelPath);
      
      // 加载模型
      console.log('开始加载模型...');
      PIXI.live2d.Live2DModel.from(modelPath, { 
        autoInteract: this.vue.eyesFollow,
        autoUpdate: true,
        idleMotionGroup: 'Idle'
      })
        .then(model => {
          console.log('模型加载成功! 原始尺寸:', model.width, 'x', model.height);
          
          // 保存原始模型尺寸
          this.modelSize = {
            width: model.width,
            height: model.height
          };
          this.vue.modelSize = this.modelSize;
          
          // 计算适合的Canvas尺寸，根据模型比例
          this.adjustCanvasSize(model);
          
          // 调整模型缩放和位置
          this.positionModel(model);
          
          // 添加到舞台
          this.app.stage.addChild(model);
          
          // 设置模型交互
          this.setupModelInteractions(model);
          
          // 保存模型引用
          this.live2dModel = model;
          this.vue.live2dModel = model;
          this.modelLoaded = true;
          this.vue.modelLoaded = true;
          
          // 更新动作和表情列表
          this.updateAvailableMotions(model);
          this.updateAvailableExpressions(model);
          
          // 初始化音频处理
          this.initAudioAnalyser();
          
          // 更新Vue组件中的状态
          this.vue.isLoading = false;
          
          console.log('Live2D初始化完成!');
        })
        .catch(error => {
          console.error('模型加载失败:', error);
          this.vue.loadingError = `模型加载失败: ${error.message || '未知错误'}`;
          this.vue.isLoading = false;
        });
        
    } catch (error) {
      console.error('初始化Live2D失败:', error);
      this.vue.loadingError = `Live2D初始化失败: ${error.message}`;
      this.vue.isLoading = false;
    }
  }
  
  /**
   * 根据模型调整Canvas尺寸
   * @param {Object} model Live2D模型对象
   */
  adjustCanvasSize(model) {
    // 确定模型实际需要的尺寸 (考虑缩放系数)
    const modelAspect = model.height / model.width;
    
    // 基于屏幕大小和模型比例确定适合的尺寸
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const maxWidth = Math.min(1200, screenWidth * 0.8); // 限制最大宽度
    
    // 根据模型比例和屏幕尺寸确定
    let canvasWidth = maxWidth;
    let canvasHeight = Math.round(canvasWidth * modelAspect);
    
    // 确保高度不超过屏幕高度的95%
    if (canvasHeight > screenHeight * 0.95) {
      canvasHeight = Math.round(screenHeight * 0.95);
      canvasWidth = Math.round(canvasHeight / modelAspect);
    }
    
    // 更新canvas尺寸
    const canvas = document.getElementById("canvas");
    if (canvas) {
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      
      // 确保透明度
      canvas.style.backgroundColor = 'transparent';
      
      // 调整PIXI应用尺寸
      if (this.app) {
        try {
          this.app.renderer.resize(canvasWidth, canvasHeight);
          
          // 确保渲染器透明度设置
          this.app.renderer.backgroundAlpha = 0;
          if (this.app.renderer.backgroundColor) {
            this.app.renderer.backgroundColor = 0x00000000;
          }
          
          // 清除渲染器
          if (this.app.renderer.clear) {
            this.app.renderer.clear();
          }
        } catch (e) {
          console.error('调整PIXI应用尺寸失败:', e);
        }
      }
      
      // 保存当前尺寸
      this.canvasSize = {
        width: canvasWidth,
        height: canvasHeight
      };
      this.vue.canvasSize = this.canvasSize;
      
      console.log('Canvas尺寸已调整为:', canvasWidth, 'x', canvasHeight);
    }
  }
  
  /**
   * 调整模型位置和缩放
   * @param {Object} model Live2D模型对象
   */
  positionModel(model) {
    // 获取当前canvas尺寸
    const canvasWidth = this.canvasSize.width;
    const canvasHeight = this.canvasSize.height;
    
    // 计算合适的缩放比例
    const scaleX = canvasWidth / model.width;
    const scaleY = canvasHeight / model.height;
    const baseScale = Math.min(scaleX, scaleY);
    
    // 应用缩放系数
    const finalScale = baseScale * this.scaleFactor;
    model.scale.set(finalScale);
    
    // 视觉上居中模型，并向左下角微调
    model.x = (canvasWidth / 2) - (canvasWidth * 0.05); //向左偏移5%
    model.y = (canvasHeight / 2) + (canvasHeight * 0.072); // 向下偏移7.2%
    
    // 设置锚点为中心
    model.anchor.set(0.5, 0.5);
    
    // 记录详细的定位信息以便调试
    console.log('模型居中定位数据:', {
      canvasSize: `${canvasWidth}x${canvasHeight}`,
      modelSize: `${model.width}x${model.height}`,
      scaledSize: `${model.width * finalScale}x${model.height * finalScale}`,
      scale: finalScale,
      position: `(${model.x}, ${model.y})`,
      anchor: `(${model.anchor.x}, ${model.anchor.y})`
    });
  }
  
  /**
   * 设置模型交互
   * @param {Object} model Live2D模型对象
   */
  setupModelInteractions(model) {
    // 添加点击交互
    model.on("hit", (hitAreas) => {
      console.log('模型被点击:', hitAreas);
      if (hitAreas.includes("Body")) {
        model.motion("Tap");
      }
      if (hitAreas.includes("Head")) {
        model.expression();
      }
    });
  }
  
  /**
   * 播放随机动作
   */
  playRandomMotion() {
    if (!this.live2dModel || !this.modelLoaded) {
      console.log('模型尚未加载，无法执行动作');
      return;
    }

    // 从Vue组件获取动作列表
    const motions = this.vue.motions;
    if (motions.length === 0) {
      console.log('模型没有可用的动作');
      return;
    }
    
    // 从动作列表中随机选择一个
    const randomIndex = Math.floor(Math.random() * motions.length);
    const randomMotion = motions[randomIndex];
    
    console.log(`播放动作: ${randomMotion}`);
    this.live2dModel.motion(randomMotion);
  }
  
  /**
   * 播放随机表情
   */
  playRandomExpression() {
    if (!this.live2dModel || !this.modelLoaded) {
      console.log('模型尚未加载，无法执行表情');
      return;
    }
    
    // 从Vue组件获取表情列表
    const expressions = this.vue.expressions;
    if (expressions.length === 0) {
      console.log('模型没有可用的表情');
      return;
    }
    
    // 从表情列表中随机选择一个
    const randomIndex = Math.floor(Math.random() * expressions.length);
    
    console.log(`播放表情索引: ${randomIndex}`);
    
    // 直接使用索引值，而不是表情名称
    this.live2dModel.expression(randomIndex);
  }
  
  /**
   * 更新可用动作列表
   * @param {Object} model Live2D模型对象
   */
  updateAvailableMotions(model) {
    try {
      // 尝试获取当前模型的动作组列表
      if (model.internalModel && model.internalModel.motionManager) {
        const motionGroups = Object.keys(model.internalModel.motionManager.definitions);
        if (motionGroups.length > 0) {
          this.motions = motionGroups;
          this.vue.motions = motionGroups;
          console.log('可用动作组:', this.motions);
        }
      }
    } catch (error) {
      console.warn('获取动作列表失败，使用默认动作:', error);
    }
  }
  
  /**
   * 更新可用表情列表
   * @param {Object} model Live2D模型对象
   */
  updateAvailableExpressions(model) {
    try {
      // 获取当前模型的表情列表
      if (model.internalModel && model.internalModel.settings && 
          model.internalModel.settings.expressions) {
        // 存储表情名称用于显示
        const availableExpressions = model.internalModel.settings.expressions.map(exp => exp.Name);
        
        if (availableExpressions.length > 0) {
          this.expressions = availableExpressions;
          this.vue.expressions = availableExpressions;
          console.log('可用表情:', this.expressions);
        }
      }
    } catch (error) {
      console.warn('获取表情列表失败:', error);
    }
  }
  
  /**
   * 初始化音频分析器
   */
  initAudioAnalyser() {
    try {
      console.log('初始化音频分析器...');
      // 由于音频上下文需要用户交互才能创建，这里先不创建
      // 将在播放音频时按需创建
      this.frequencyData = new Uint8Array(16); // 预先创建频率数据数组
      console.log('音频分析器预备完成');
    } catch (error) {
      console.error('初始化音频分析器预备失败:', error);
    }
  }
  
  /**
   * 播放音频并同步口型
   * @param {string} url 音频URL
   */
  playAudio(url) {
    console.log('开始播放音频并同步口型:', url);
    
    if (this.live2dModel && this.modelLoaded) {
      // 使用模型自带的speak功能播放音频
      this.talk(this.live2dModel, url);
    } else {
      // 无模型时创建独立音频元素播放
      const audio = new Audio(url);

      
      audio.play().catch(error => {
        console.error('音频播放失败:', error);
        if (error.name === 'NotAllowedError') {
          console.log('需要用户交互才能播放音频');
          this.startSimulatedMouthTracking();
        } else {
          this.stopSpeaking();
        }
      });
    }
  }
  
  /**
   * 控制模型说话
   * @param {Object} model Live2D模型对象
   * @param {string} audio 音频URL
   */
  talk(model, audio) {
    try {
      // 使用模型自带的speak功能，配置最佳的口型同步参数
      model.speak(audio, {

        expression: this.vue.expressions.length > 8 ? 8 : 0, // 如果有足够的表情，使用第8个，否则用默认表情
        resetExpression: true,    // 说话完成后重置表情
        autoPlay: true,           // 自动播放音频
        crossOrigin: "anonymous", // 允许跨域音频
        onFinish: () => {         // 播放完成后的回调
          console.log('模型speak播放完成');
          this.stopSpeaking();
        },
        onError: (e) => {         // 出错处理
          console.error('模型speak出错:', e);
          // 回退到标准播放方法
          this.fallbackToStandardPlayback(audio);
        }
      });
      
      // 设置说话状态
      this.vue.isSpeaking = true;
    } catch (error) {
      console.error('使用模型speak功能失败:', error);
      // 回退到标准播放方法
      this.fallbackToStandardPlayback(audio);
    }
  }
  
  /**
   * 回退到标准音频播放方法
   * @param {string} url 音频URL
   */
  fallbackToStandardPlayback(url) {
    console.log('回退到标准音频播放方法');
    
    try {
      // 初始化音频上下文
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.audioAnalyser = this.audioContext.createAnalyser();
        this.audioAnalyser.fftSize = 32;
        this.frequencyData = new Uint8Array(this.audioAnalyser.frequencyBinCount);
      }
      
      const audioPlayer = this.vue.$refs.audioPlayer;
      audioPlayer.src = url;
      audioPlayer.load();
      audioPlayer.muted = true;
      
      // 连接音频分析器
      if (this.audioContext && this.audioAnalyser) {
        if (this.audioSource) {
          try { this.audioSource.disconnect(); } catch (e) { /* 忽略错误 */ }
        }
        
        this.audioSource = this.audioContext.createMediaElementSource(audioPlayer);
        this.audioSource.connect(this.audioAnalyser);
        this.audioAnalyser.connect(this.audioContext.destination);
        
        // 开始口型跟踪
        //this.startMouthTracking();
      }
      
    //   // 播放音频
    //   audioPlayer.play().catch(e => {
    //     console.error('回退播放也失败:', e);
    //     // 使用模拟口型
    //     this.startSimulatedMouthTracking();
    //   });
    } catch (error) {
      console.error('回退播放方法出错:', error);
      // 最后的尝试：使用模拟口型
      this.startSimulatedMouthTracking();
    }
  }
  
  /**
   * 开始跟踪口型
   */
  startMouthTracking() {
    console.log('开始跟踪口型');
    
    // 如果已经在跟踪，则先停止
    if (this.mouthUpdateInterval) {
      this.app.ticker.remove(this.mouthUpdateInterval);
      this.mouthUpdateInterval = null;
    }
    
    // 定义口型同步循环
    const mouthSyncLoop = () => {
      // 分析音频数据，更新口型
      if (this.audioAnalyser && this.frequencyData) {
        try {
          this.audioAnalyser.getByteFrequencyData(this.frequencyData);
          
          // 计算音量，关注低频和中频段
          let sum = 0;
          // 只使用前半部分频率数据，这通常对应人声频率
          const relevantDataLength = Math.min(8, this.frequencyData.length);
          for (let i = 0; i < relevantDataLength; i++) {
            sum += this.frequencyData[i];
          }
          
          const average = sum / relevantDataLength;
          
          // 映射到口型开合值 (0-1 范围)，增加灵敏度
          this.mouthOpenValue = Math.min(average / 64, 1) * 0.8;
          
          // 添加随机变化使口型更自然
          const randomVariation = (Math.random() * 0.1) - 0.05; // -0.05到0.05的随机值
          this.mouthOpenValue = Math.max(0, Math.min(1, this.mouthOpenValue + randomVariation));
          
          // 更新模型口型
          this.updateMouthForm();
          
          // 输出调试信息，每秒一次
          if (Date.now() % 1000 < 50) {
            console.log('当前口型值:', this.mouthOpenValue, '平均音量:', average);
          }
        } catch (e) {
          console.warn('获取频率数据失败:', e);
        }
      } else {
        console.warn('音频分析器或频率数据未初始化');
      }
    };
    
    // 添加到PIXI的ticker
    this.app.ticker.add(mouthSyncLoop);
    this.mouthUpdateInterval = mouthSyncLoop; // 保存循环函数引用
  }

  
  /**
   * 更新模型口型参数
   */
  updateMouthForm() {
    if (!this.live2dModel || !this.modelLoaded) return;
    
    try {
      // 列出可能的口型参数名，按常见程度排序
      const possibleParams = [
        'ParamMouthOpenY',
        'PARAM_MOUTH_OPEN_Y', 
        'Param_Mouth_Open',
        'ParamMouthOpen',
        'ParamMouthOpenB', // 有些模型使用B变体
        'PARAM_MOUTH_FORM', // 口型形状参数
        'Mouth' // 简化名称
      ];
      
      // 使用一个附加参数来控制口型形状
      const formParams = [
        'ParamMouthForm',
        'PARAM_MOUTH_FORM'
      ];
      
      let paramFound = false;
      
      // 尝试找到并设置口型参数
      for (const param of possibleParams) {
        if (this.live2dModel.internalModel && 
            this.live2dModel.internalModel.coreModel) {
          
          // 使用获取参数索引的方法
          try {
            const index = this.live2dModel.internalModel.coreModel.getParameterIndex(param);
            if (index !== -1) {
              // 找到可用参数，保存它
              this.mouthOpenParamName = param;
              
              // 设置值
              this.live2dModel.internalModel.coreModel.setParameterValueById(param, this.mouthOpenValue);
              paramFound = true;
              break;
            }
          } catch (e) {
            // 这个方法不可用，尝试下一个
            console.warn(`使用getParameterIndex('${param}')失败:`, e);
          }
          
          // 尝试使用通用参数设置
          try {
            this.live2dModel.internalModel.coreModel.setParameterValueById(param, this.mouthOpenValue);
            this.mouthOpenParamName = param;
            paramFound = true;
            break;
          } catch (e) {
            // 这个方法或参数不可用，继续尝试
            continue;
          }
        }
      }
      
      // 设置口型形状参数(如果找到合适的)
      if (paramFound && this.mouthOpenValue > 0.2) {
        // 当嘴巴张开时，尝试设置口型形状
        for (const formParam of formParams) {
          try {
            const formValue = 0.5; // 中性口型形状
            this.live2dModel.internalModel.coreModel.setParameterValueById(formParam, formValue);
          } catch (e) {
            // 参数不可用，继续尝试
            continue;
          }
        }
      }
      
      // 如果没找到合适的参数，尝试使用模型的现有方法
      if (!paramFound) {
        try {
          // 检查模型是否有直接的说话方法
          if (typeof this.live2dModel.speak === 'function') {
            // 标记为使用内置方法
            this.usingBuiltInSpeech = true;
          } else {
            console.warn('未找到合适的口型参数，口型同步可能无法正常工作');
          }
        } catch (e) {
          console.warn('检查内置说话方法失败:', e);
        }
      }
    } catch (error) {
      console.warn('更新口型参数失败:', error);
    }
  }
  
  /**
   * 停止说话动画
   */
  stopSpeaking() {
    console.log('停止说话动画');
    this.vue.isSpeaking = false;
    
    // 优先使用模型自带的停止说话方法
    if (this.live2dModel) {
      if (typeof this.live2dModel.stopSpeaking === 'function') {
        try {
          this.live2dModel.stopSpeaking();
        } catch (e) {
          console.warn('模型stopSpeaking方法出错:', e);
        }
      }
    }
    
    // 停止音频播放
    const audioPlayer = this.vue.$refs.audioPlayer;
    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer.currentTime = 0;
    }
    
    // 停止口型更新
    if (this.mouthUpdateInterval) {
      this.app.ticker.remove(this.mouthUpdateInterval);
      this.mouthUpdateInterval = null;
    }
    
    // 重置口型
    this.mouthOpenValue = 0;
    this.updateMouthForm();
  }
}
