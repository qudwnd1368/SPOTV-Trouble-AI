SEED_KNOWLEDGE_ITEMS = [
    {
        "title": "EVS XT2 IN-A 입력 불량",
        "context": "EVS XT-2 IN-A 채널에 SDI 입력이 정상적으로 들어오지 않는 상황.",
        "action": "COHX 보드 불량 여부를 확인하고, 필요 시 COHX 보드를 교체한 뒤 정상 입력 여부를 확인한다.",
        "caution": "A2 버전 보드 호환성을 우선 확인하고, 방송 중에는 입력 라우팅 변경을 신중하게 진행한다.",
    },
    {
        "title": "vMix 스트림덱 버튼 반응 불량",
        "context": "스트림덱 버튼에 빨간불이 들어오고 vMix 제어가 반응하지 않는 상황.",
        "action": "Bitfocus Companion 또는 스트림덱 관련 소프트웨어를 종료한 뒤 다시 실행한다.",
        "caution": "재시작 전 현재 방송 제어 상태를 확인하고, 온에어 중인 버튼 동작은 임의로 반복 입력하지 않는다.",
    },
    {
        "title": "EVS XT2 아날로그 오디오 입출력 불량",
        "context": "EVS XT-2에서 아날로그 오디오 입력 또는 출력이 정상적으로 동작하지 않는 상황.",
        "action": "오디오 코덱 보드 상태를 확인하고, 불량으로 판단되면 보드 교체 후 입출력을 다시 점검한다.",
        "caution": "교체 전 케이블, 라우팅, 채널 설정 문제인지 먼저 확인한다.",
    },
    {
        "title": "vMix VCR 재생 멈춤",
        "context": "Companion 버튼을 빠르게 연속 입력하면 다음 VCR 영상이 첫 프레임에서 멈추는 상황.",
        "action": "Companion vMix 모듈을 업데이트하고, 상태 판단 로직을 Companion에서 처리하도록 명령을 단순화한다.",
        "caution": "방송 중 바로 적용하지 말고 사전 테스트 환경에서 버튼 입력 조건을 충분히 확인한 뒤 적용한다.",
    },
    {
        "title": "Yamaha CL3 페이더 떨림 및 송출 잔류",
        "context": "Yamaha CL3에서 페이더를 내려도 소리가 송출되고 9-16번 페이더가 떨리는 상황.",
        "action": "9-16번 페이더 모터 상태를 확인하고, 불량이면 페이더 모듈을 교체한다.",
        "caution": "교체 전 씬 설정, DCA, 믹스버스 라우팅 때문에 소리가 남는 상황은 아닌지 먼저 확인한다.",
    },
]


# Backward-compatible name for older imports.
SEED_INCIDENTS = SEED_KNOWLEDGE_ITEMS
