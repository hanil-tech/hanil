' 원본: Declaration.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module Declaration

    Public Return_Value1 As Long
    Public Return_Value2 As Long
    Public Status_Value As Integer

    Public LogoFile As String
    Public CName As String

    Public Customer As String
    Public tD2NO As Double
    Public q As Double
    Public pt As Double
    Public ps As Double

    Public temp As Double
    Public gamma As Double
    Public ns As Double
    Public N As Double
    Public D2 As Double
    Public D2no As Double
    Public sigma As Double
    Public delta As Double
    Public D1 As Double
    Public diaratio As Double
    Public b1 As Double
    Public b2 As Double
    Public bt As Double
    Public Z As Integer
    Public spower As Double
    Public DS As Double
    Public motorPulley As Double
    Public fanPulley As Double
    Public PCS As Integer ' VPulley 가닥수

    Public Lout As Integer
    Public Wout As Integer

    Public myy As Double
    Public myr As Double
    Public beta1 As Double
    Public u2 As Double
    Public u1 As Double
    Public ku As Double
    Public VbeltType As String
    Public material As String
    Public errCheck As Boolean
    Public motoroutput As String
    Public motorvoltage As String
    Public motorpoles As String
    Public motorcapa As Double
    Public motorframe As String
    Public motorrpm As Integer
    Public motoreff As Double
    Public motorpf As Double
    Public motorloadamp As Double
    Public motorstartamp As Double
    Public motorloadtor As Double
    Public motorstarttor As Double
    Public motormaxtor As Double
    Public motorgd2 As Double
    Public motorwt As Double
    Public drvmethod As String
    Public mtPower As Double
    Public nRatio As Double
    Public SPL As Double
    Public bearingno As Integer
    Public maxStress As Integer
    Public sWeight As Integer
    Public mStress As Double
    Public bladeStress As Double
    Public mSf As Double
    Public bSf As Double
    Public Lh As Double
    Public LhYear As Double
    Public LhMonth As Integer
    Public FanEff As Double
    Public DiaInlet As Double
    Public PassWord As String
    Public vi As Double
    Public Direction As String
    Public Bool_Motor_Sel As Boolean

    Public SmallestSize As Double
    Public BiggestSize As Double
    Public sFanPulley As Double
    Public sMotorPulley As Double

    Public fromcobVBelt As Boolean

    'pdf 보기

End Module
