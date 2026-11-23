Attribute VB_Name = "VBelt"
Option Explicit
Public Sub Vbelt_Type_Reselection() '재계산 (증가)

    Dim K As Double
    Dim L As Double
    Dim ratio As Double
    
    
    If VbeltType = "A Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 30 Step 0.5
            For L = SmallestSize To 30 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
    End If
    
    If VbeltType = "B Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 50 Step 0.5
            For L = SmallestSize To 50 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "C Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 80 Step 0.5
            For L = SmallestSize To 80 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "D Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 140 Step 0.5
            For L = SmallestSize To 140 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "3V Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 140 Step 0.5
            For L = SmallestSize To 140 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "5V Type" Then
        'Pulley 직경 선정
        For K = SmallestSize To 140 Step 0.5
            For L = SmallestSize To 140 Step 0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
JUMP1:
    
    'Pulley경 및 회전수 Swifing
    Dim smallPulley As Double
    Dim smallPulleyrpm As Double
    
    If nRatio >= 1 Then
        smallPulleyrpm = N
        If K > L Then
            motorPulley = K
            fanPulley = L
            smallPulley = L
        Else
            motorPulley = L
            fanPulley = K
            smallPulley = K
        End If
    Else
        smallPulleyrpm = motorrpm
        If K > L Then
            motorPulley = L
            fanPulley = K
            smallPulley = L
        Else
            motorPulley = K
            fanPulley = L
            smallPulley = K
        End If
    End If
    
    If fromcobVBelt = True Then
        sFanPulley = fanPulley
        sMotorPulley = motorPulley
    End If
    
    Dim speed As Double
        speed = (Atn(1) * 4) * smallPulley * motorrpm / 12000
    
    'V-Belt 1가닥당 전동마력 계산
    Dim hpt As Double
    
    If VbeltType = "A Type" Then
        hpt = (1.589 - 2.702 / smallPulley - 0.0146 * speed ^ 2) * speed
    End If
    
    If VbeltType = "B Type" Then
        hpt = (2.822 - 7.725 / smallPulley - 0.0251 * speed ^ 2) * speed
    End If
    
    If VbeltType = "C Type" Then
        hpt = (5.822 - 26.971 / smallPulley - 0.0379 * speed ^ 2) * speed
    End If
    
    If VbeltType = "D Type" Then
        hpt = (12.628 - 96.991 / smallPulley - 0.0815 * speed ^ 2) * speed
    End If
    
    Dim vRatio As Double
    Dim kr As Double
    
    vRatio = N / motorrpm
    If vRatio < 1 Then
        vRatio = 1 / vRatio
    End If
    
    '3V Type에 대한 계산
    If VbeltType = "3V Type" Then
        Select Case vRatio
            Case Is <= 1.02
                kr = 0
            Case 1.02 To 1.06
                kr = 0.0000198
            Case 1.06 To 1.11
                kr = 0.000054
            Case 1.11 To 1.19
                kr = 0.0000941
            Case 1.19 To 1.27
                kr = 0.000123
            Case 1.27 To 1.39
                kr = 0.000155
            Case 1.39 To 1.58
                kr = 0.000182
            Case 1.58 To 1.95
                kr = 0.000205
            Case 1.95 To 3.39
                kr = 0.000223
            Case Is > 3.39
                kr = 0.000236
        End Select
        
        Dim factor1 As Double
        Dim factor2 As Double
        Dim factor3 As Double
        Dim factor4 As Double
        Dim factor5 As Double
        
        factor1 = smallPulley * 25 * smallPulleyrpm
        factor2 = 0.000085145
        factor3 = 0.0020844 / (smallPulley * 25)
        factor4 = 1.3435E-17 * (smallPulley * 25 * smallPulleyrpm) ^ 2
        factor5 = 0.0000076008 * (Log(smallPulley * 25) / Log(10) + Log(smallPulleyrpm) / Log(10))
        
        hpt = factor1 * (factor2 - factor3 - factor4 - factor5) + kr * smallPulleyrpm
        
    End If
    
    '5V Type에 대한 계산
    
    If VbeltType = "5V Type" Then
    
        Select Case vRatio
            Case Is <= 1.02
                kr = 0
            Case 1.02 To 1.06
                kr = 0.000112
            Case 1.06 To 1.11
                kr = 0.000306
            Case 1.11 To 1.19
                kr = 0.000533
            Case 1.19 To 1.27
                kr = 0.000725
            Case 1.27 To 1.39
                kr = 0.000879
            Case 1.39 To 1.58
                kr = 0.00103
            Case 1.58 To 1.95
                kr = 0.00116
            Case 1.95 To 3.39
                kr = 0.00126
            Case Is > 3.39
                kr = 0.00134
        End Select
    
        factor1 = smallPulley * 25 * smallPulleyrpm
        factor2 = 0.00024535
        factor3 = 0.0118 / (smallPulley * 25)
        factor4 = 4.1072E-17 * (smallPulley * 25 * smallPulleyrpm) ^ 2
        factor5 = 0.000021353 * (Log(smallPulley * 25) / Log(10) + Log(smallPulleyrpm) / Log(10))
        
        hpt = factor1 * (factor2 - factor3 - factor4 - factor5) + kr * smallPulleyrpm
        
    End If
    
    If hpt < 1 Then hpt = 1
    
    Dim spowerhp As Double
    spowerhp = spower * 1.36
    PCS = Int(spowerhp / hpt) + 1
    
    '재계산된 Pulley경 출력폼에 출력
    frmOutput.txtPulleySizeFan.text = fanPulley & " ˝"
    frmOutput.txtPulleySizeMotor.text = motorPulley & " ˝"

End Sub

Public Sub Vbelt_Type_Reselection1() '재계산 (감소)
    
    Dim K As Double
    Dim L As Double
    Dim ratio As Double
    
    If VbeltType = "A Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 3 Step -0.5
            For L = BiggestSize To 3 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
    End If
    
    If VbeltType = "B Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 5 Step -0.5
            For L = BiggestSize To 5 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "C Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 8 Step -0.5
            For L = BiggestSize To 8 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "D Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 14 Step -0.5
            For L = BiggestSize To 14 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "3V Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 5 Step -0.5
            For L = BiggestSize To 5 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
    If VbeltType = "5V Type" Then
        'Pulley 직경 선정
        For K = BiggestSize To 8 Step -0.5
            For L = BiggestSize To 8 Step -0.5
                ratio = L / K
                If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
            Next L
        Next K
        
    End If
    
JUMP1:
    
    'Pulley경 및 회전수 Swifing
    Dim smallPulley As Double
    Dim smallPulleyrpm As Double
    
    If nRatio >= 1 Then
        smallPulleyrpm = N
        If K > L Then
            motorPulley = K
            fanPulley = L
            smallPulley = L
        Else
            motorPulley = L
            fanPulley = K
            smallPulley = K
        End If
    Else
        smallPulleyrpm = motorrpm
        If K > L Then
            motorPulley = L
            fanPulley = K
            smallPulley = L
        Else
            motorPulley = K
            fanPulley = L
            smallPulley = K
        End If
    End If
    
    Dim speed As Double
        speed = (Atn(1) * 4) * smallPulley * motorrpm / 12000
    
    'V-Belt 1가닥당 전동마력 계산
    Dim hpt As Double
    
    If VbeltType = "A Type" Then
        hpt = (1.589 - 2.702 / smallPulley - 0.0146 * speed ^ 2) * speed
    End If
    
    If VbeltType = "B Type" Then
        hpt = (2.822 - 7.725 / smallPulley - 0.0251 * speed ^ 2) * speed
    End If
    
    If VbeltType = "C Type" Then
        hpt = (5.822 - 26.971 / smallPulley - 0.0379 * speed ^ 2) * speed
    End If
    
    If VbeltType = "D Type" Then
        hpt = (12.628 - 96.991 / smallPulley - 0.0815 * speed ^ 2) * speed
    End If
    
    Dim vRatio As Double
    Dim kr As Double
    
    vRatio = N / motorrpm
    If vRatio < 1 Then
        vRatio = 1 / vRatio
    End If
    
    '3V Type에 대한 계산
    If VbeltType = "3V Type" Then
        Select Case vRatio
            Case Is <= 1.02
                kr = 0
            Case 1.02 To 1.06
                kr = 0.0000198
            Case 1.06 To 1.11
                kr = 0.000054
            Case 1.11 To 1.19
                kr = 0.0000941
            Case 1.19 To 1.27
                kr = 0.000123
            Case 1.27 To 1.39
                kr = 0.000155
            Case 1.39 To 1.58
                kr = 0.000182
            Case 1.58 To 1.95
                kr = 0.000205
            Case 1.95 To 3.39
                kr = 0.000223
            Case Is > 3.39
                kr = 0.000236
        End Select
        
        Dim factor1 As Double
        Dim factor2 As Double
        Dim factor3 As Double
        Dim factor4 As Double
        Dim factor5 As Double
        
        factor1 = smallPulley * 25 * smallPulleyrpm
        factor2 = 0.000085145
        factor3 = 0.0020844 / (smallPulley * 25)
        factor4 = 1.3435E-17 * (smallPulley * 25 * smallPulleyrpm) ^ 2
        factor5 = 0.0000076008 * (Log(smallPulley * 25) / Log(10) + Log(smallPulleyrpm) / Log(10))
        
        hpt = factor1 * (factor2 - factor3 - factor4 - factor5) + kr * smallPulleyrpm
        
    End If
    
    '5V Type에 대한 계산
    
    If VbeltType = "5V Type" Then
    
        Select Case vRatio
            Case Is <= 1.02
                kr = 0
            Case 1.02 To 1.06
                kr = 0.000112
            Case 1.06 To 1.11
                kr = 0.000306
            Case 1.11 To 1.19
                kr = 0.000533
            Case 1.19 To 1.27
                kr = 0.000725
            Case 1.27 To 1.39
                kr = 0.000879
            Case 1.39 To 1.58
                kr = 0.00103
            Case 1.58 To 1.95
                kr = 0.00116
            Case 1.95 To 3.39
                kr = 0.00126
            Case Is > 3.39
                kr = 0.00134
        End Select
    
        factor1 = smallPulley * 25 * smallPulleyrpm
        factor2 = 0.00024535
        factor3 = 0.0118 / (smallPulley * 25)
        factor4 = 4.1072E-17 * (smallPulley * 25 * smallPulleyrpm) ^ 2
        factor5 = 0.000021353 * (Log(smallPulley * 25) / Log(10) + Log(smallPulleyrpm) / Log(10))
        
        hpt = factor1 * (factor2 - factor3 - factor4 - factor5) + kr * smallPulleyrpm
        
    End If
    
    If hpt < 1 Then hpt = 1
    
    Dim spowerhp As Double
    spowerhp = spower * 1.36
    PCS = Int(spowerhp / hpt) + 1
    
    '재계산된 Pulley경 출력폼에 출력
    frmOutput.txtPulleySizeFan.text = fanPulley & " ˝"
    frmOutput.txtPulleySizeMotor.text = motorPulley & " ˝"

End Sub

